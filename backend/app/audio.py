"""Microphone capture with VAD-based phrase chunking and trailing-silence trim."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

import numpy as np
import sounddevice as sd
import webrtcvad

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
FRAME_MS = 30
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)
TRAILING_SILENCE_MS = 600
TRAILING_SILENCE_FRAMES = TRAILING_SILENCE_MS // FRAME_MS

# Phrase chunking: emit a chunk after this much continuous silence
CHUNK_SILENCE_MS = 500
CHUNK_SILENCE_FRAMES = CHUNK_SILENCE_MS // FRAME_MS
MIN_CHUNK_SPEECH_FRAMES = int(300 / FRAME_MS)  # ignore chunks with <300ms of speech


def list_input_devices() -> list[dict]:
    devices = sd.query_devices()
    default_idx = sd.default.device[0]
    return [
        {"id": str(idx), "name": d["name"], "is_default": idx == default_idx}
        for idx, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]


class AudioRecorder:
    """Records audio and emits phrase chunks in real-time via on_chunk callback.

    When VAD detects CHUNK_SILENCE_MS of silence after speech, the buffered
    frames are emitted as a chunk and the buffer resets. stop() returns any
    remaining audio since the last chunk boundary.
    """

    def __init__(
        self,
        device: str | None = None,
        vad_aggressiveness: int = 2,
        on_chunk: Callable[[np.ndarray], None] | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._device = int(device) if device is not None else None
        self._vad = webrtcvad.Vad(vad_aggressiveness)
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._on_chunk = on_chunk
        self._loop = loop
        # VAD state (reset on start)
        self._speech_frames_since_chunk = 0
        self._consecutive_silent = 0
        self._had_speech = False

    def start(self) -> None:
        self._frames = []
        self._speech_frames_since_chunk = 0
        self._consecutive_silent = 0
        self._had_speech = False

        def callback(indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
            if status:
                logger.warning("audio stream status: %s", status)
            self._frames.append(indata.copy())

            # Run VAD on this frame
            pcm16 = (indata.flatten()[:FRAME_SAMPLES] * 32768).astype(np.int16)
            is_speech = False
            if len(pcm16) == FRAME_SAMPLES:
                try:
                    is_speech = self._vad.is_speech(pcm16.tobytes(), SAMPLE_RATE)
                except Exception:
                    pass

            if is_speech:
                self._had_speech = True
                self._speech_frames_since_chunk += 1
                self._consecutive_silent = 0
            else:
                self._consecutive_silent += 1

            # Emit chunk when sustained silence follows enough speech
            if (
                self._on_chunk
                and self._had_speech
                and self._consecutive_silent >= CHUNK_SILENCE_FRAMES
                and self._speech_frames_since_chunk >= MIN_CHUNK_SPEECH_FRAMES
            ):
                chunk = np.concatenate(self._frames, axis=0).flatten()
                self._frames = []
                self._had_speech = False
                self._speech_frames_since_chunk = 0
                self._consecutive_silent = 0
                if self._loop:
                    self._loop.call_soon_threadsafe(self._on_chunk, chunk)

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=FRAME_SAMPLES,
            device=self._device,
            callback=callback,
        )
        self._stream.start()
        logger.info("recording started")

    def stop(self) -> np.ndarray:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("recording stopped")
        if not self._frames:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self._frames, axis=0).flatten()

    def trim_trailing_silence(self, audio: np.ndarray) -> np.ndarray:
        """Drop trailing silence using webrtcvad, frame by frame."""
        if audio.size == 0:
            return audio
        pcm16 = (audio * 32768).astype(np.int16)
        n_frames = len(pcm16) // FRAME_SAMPLES
        last_voiced_frame = n_frames
        for i in range(n_frames):
            frame = pcm16[i * FRAME_SAMPLES : (i + 1) * FRAME_SAMPLES].tobytes()
            if self._vad.is_speech(frame, SAMPLE_RATE):
                last_voiced_frame = i + 1
        cutoff = min(last_voiced_frame + TRAILING_SILENCE_FRAMES, n_frames)
        return audio[: cutoff * FRAME_SAMPLES]
