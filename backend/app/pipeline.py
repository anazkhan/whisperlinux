"""Async pipeline orchestrator: audio → STT → Gemini cleanup → injection.

Phrase-level streaming: while recording, each natural speech pause triggers
background transcription of that phrase. By the time the user clicks Done,
most of the audio is already transcribed — only the last short phrase remains.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import numpy as np

from app.audio import AudioRecorder
from app.cleanup.gemini import CleanupError, GeminiCleaner
from app.config import get_gemini_api_key, load_settings
from app.injection.base import get_injector
from app.schemas import HistoryEntry, StatusEvent
from app.stt.engine import SttEngine

logger = logging.getLogger(__name__)

status_bus: asyncio.Queue[StatusEvent] = asyncio.Queue()
history: list[HistoryEntry] = []

_SENTINEL = None  # signals background transcriber to stop


class Pipeline:
    def __init__(self) -> None:
        settings = load_settings()
        self._stt = SttEngine(model_size=settings.stt_model, device=settings.stt_device)
        self._recorder: AudioRecorder | None = None
        self._recording = False
        self._state = "idle"
        self._lock = asyncio.Lock()
        # Phrase chunking state
        self._partial_texts: list[str] = []
        self._chunk_queue: asyncio.Queue | None = None
        self._transcribe_task: asyncio.Task | None = None

    # ── Public interface ───────────────────────────────────────────────────────

    async def toggle(self) -> None:
        final_audio = await self._do_stop()
        if final_audio is not None:
            asyncio.create_task(self._process(final_audio))
        else:
            async with self._lock:
                if not self._recording:
                    await self._start_recording()

    async def start(self) -> None:
        async with self._lock:
            if not self._recording:
                await self._start_recording()

    async def stop(self) -> None:
        final_audio = await self._do_stop()
        if final_audio is not None:
            asyncio.create_task(self._process(final_audio))

    def reload_stt(self) -> None:
        settings = load_settings()
        self._stt.reload(model_size=settings.stt_model, device=settings.stt_device)

    # ── Internal ───────────────────────────────────────────────────────────────

    async def _start_recording(self) -> None:
        settings = load_settings()
        self._partial_texts = []
        self._chunk_queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_chunk(audio: np.ndarray) -> None:
            if self._chunk_queue is not None:
                self._chunk_queue.put_nowait(audio)

        self._recorder = AudioRecorder(
            device=settings.mic_device,
            on_chunk=on_chunk,
            loop=loop,
        )
        self._recorder.start()
        self._recording = True
        self._state = "recording"
        self._transcribe_task = asyncio.create_task(self._background_transcribe())
        await self._emit("recording")

    async def _background_transcribe(self) -> None:
        """Drain phrase chunks from the queue and transcribe them as they arrive."""
        settings = load_settings()
        while True:
            chunk = await self._chunk_queue.get()
            if chunk is _SENTINEL:
                break
            trimmed = self._recorder.trim_trailing_silence(chunk) if self._recorder else chunk
            if trimmed.size == 0:
                continue
            try:
                text = await asyncio.get_event_loop().run_in_executor(
                    None, self._stt.transcribe, trimmed, settings.language
                )
                if text.strip():
                    self._partial_texts.append(text.strip())
                    logger.info("phrase transcribed: %s", text.strip()[:60])
            except Exception as exc:
                logger.warning("background STT error: %s", exc)

    async def _do_stop(self) -> np.ndarray | None:
        """Stop the mic quickly (lock only covers this). Returns final audio."""
        async with self._lock:
            if not self._recording:
                return None
            assert self._recorder is not None
            final_audio = self._recorder.stop()
            self._recording = False
            self._state = "transcribing"

        # Signal background transcriber to stop after current chunk
        if self._chunk_queue is not None:
            await self._chunk_queue.put(_SENTINEL)

        return final_audio

    async def _process(self, final_audio: np.ndarray) -> None:
        """Wait for background transcription, transcribe final chunk, then clean+inject."""
        # Wait for all background phrase transcriptions to finish
        if self._transcribe_task is not None:
            await self._transcribe_task
            self._transcribe_task = None

        await self._emit("transcribing")
        settings = load_settings()

        # Transcribe the final phrase (audio since last chunk boundary)
        final_text = ""
        if self._recorder and final_audio.size > 0:
            trimmed = self._recorder.trim_trailing_silence(final_audio)
            if trimmed.size > 0:
                try:
                    final_text = await asyncio.get_event_loop().run_in_executor(
                        None, self._stt.transcribe, trimmed, settings.language
                    )
                except Exception as exc:
                    logger.exception("STT error on final chunk")
                    self._state = "idle"
                    await self._emit("error", detail=str(exc))
                    return

        # Combine all phrase transcriptions
        parts = self._partial_texts + ([final_text.strip()] if final_text.strip() else [])
        self._partial_texts = []
        raw_text = " ".join(parts)

        if not raw_text.strip():
            self._state = "idle"
            await self._emit("done", detail="(no speech detected)")
            return

        # Gemini cleanup
        self._state = "cleaning_up"
        await self._emit("cleaning_up")
        api_key = get_gemini_api_key()
        cleanup_skipped = False
        cleaned_text = raw_text

        if api_key:
            cleaner = GeminiCleaner(api_key=api_key, model=settings.gemini_model)
            try:
                cleaned_text = await asyncio.get_event_loop().run_in_executor(
                    None, cleaner.clean, raw_text
                )
            except CleanupError as exc:
                logger.warning("Gemini cleanup failed, using raw transcript: %s", exc)
                cleanup_skipped = True
        else:
            logger.warning("No Gemini API key — skipping cleanup")
            cleanup_skipped = True

        # Inject
        self._state = "injecting"
        await self._emit("injecting")
        try:
            injector = get_injector()
            await asyncio.get_event_loop().run_in_executor(
                None, injector.type_text, cleaned_text
            )
        except Exception as exc:
            logger.exception("Injection error")
            self._state = "idle"
            await self._emit("error", detail=str(exc))
            return

        entry = HistoryEntry(
            timestamp=datetime.now(tz=timezone.utc),
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            cleanup_skipped=cleanup_skipped,
        )
        history.append(entry)
        if len(history) > 200:
            history.pop(0)

        self._state = "idle"
        await self._emit("done", entry=entry)

    async def _emit(self, state: str, detail: str | None = None, entry: HistoryEntry | None = None) -> None:
        event = StatusEvent(state=state, detail=detail, entry=entry)
        await status_bus.put(event)
        logger.info("pipeline: %s", state)


_pipeline: Pipeline | None = None


def get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline()
    return _pipeline
