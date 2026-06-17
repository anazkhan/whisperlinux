"""Async pipeline orchestrator: audio → STT → Gemini cleanup → injection.

Status transitions are broadcast to all connected WebSocket clients via the
global `status_bus` asyncio.Queue so the React UI stays in sync in real time.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.audio import AudioRecorder
from app.cleanup.gemini import CleanupError, GeminiCleaner
from app.config import get_gemini_api_key, load_settings
from app.injection.base import get_injector
from app.schemas import HistoryEntry, StatusEvent
from app.stt.engine import SttEngine

logger = logging.getLogger(__name__)

# In-process event bus: pipeline pushes StatusEvents, WS route fans them out.
status_bus: asyncio.Queue[StatusEvent] = asyncio.Queue()

# In-memory dictation history (cleared on restart; persistent storage is future work).
history: list[HistoryEntry] = []


class Pipeline:
    def __init__(self) -> None:
        settings = load_settings()
        self._stt = SttEngine(model_size=settings.stt_model, device=settings.stt_device)
        self._recorder: AudioRecorder | None = None
        self._recording = False
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public interface (called from hotkey trigger + REST /dictate routes)
    # ------------------------------------------------------------------

    async def toggle(self) -> None:
        async with self._lock:
            if self._recording:
                await self._stop_and_process()
            else:
                await self._start_recording()

    async def start(self) -> None:
        async with self._lock:
            if not self._recording:
                await self._start_recording()

    async def stop(self) -> None:
        async with self._lock:
            if self._recording:
                await self._stop_and_process()

    def reload_stt(self) -> None:
        settings = load_settings()
        self._stt.reload(model_size=settings.stt_model, device=settings.stt_device)

    # ------------------------------------------------------------------
    # Internal pipeline steps
    # ------------------------------------------------------------------

    async def _start_recording(self) -> None:
        settings = load_settings()
        self._recorder = AudioRecorder(device=settings.mic_device)
        self._recorder.start()
        self._recording = True
        await self._emit("recording")

    async def _stop_and_process(self) -> None:
        assert self._recorder is not None
        audio = self._recorder.stop()
        audio = self._recorder.trim_trailing_silence(audio)
        self._recorder = None
        self._recording = False

        await self._emit("transcribing")
        settings = load_settings()
        try:
            raw_text = await asyncio.get_event_loop().run_in_executor(
                None, self._stt.transcribe, audio, settings.language
            )
        except Exception as exc:
            logger.exception("STT error")
            await self._emit("error", detail=str(exc))
            return

        if not raw_text.strip():
            await self._emit("done", detail="(no speech detected)")
            return

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
            logger.warning("No Gemini API key set — skipping cleanup")
            cleanup_skipped = True

        await self._emit("injecting")
        try:
            injector = get_injector()
            await asyncio.get_event_loop().run_in_executor(
                None, injector.type_text, cleaned_text
            )
        except Exception as exc:
            logger.exception("Injection error")
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

        await self._emit("done", entry=entry)

    async def _emit(
        self,
        state: str,
        detail: str | None = None,
        entry: HistoryEntry | None = None,
    ) -> None:
        event = StatusEvent(state=state, detail=detail, entry=entry)
        await status_bus.put(event)
        logger.debug("pipeline state: %s", state)


# Singleton instance, created on first import by main.py after startup.
_pipeline: Pipeline | None = None


def get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline()
    return _pipeline
