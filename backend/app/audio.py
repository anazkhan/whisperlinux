"""Microphone capture with voice-activity-based trailing-silence trim."""
from __future__ import annotations

import collections
import logging

import numpy as np
import sounddevice as sd
import webrtcvad

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
FRAME_MS = 30
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)
TRAILING_SILENCE_MS = 600
TRAILING_SILENCE_FRAMES = TRAILING_SILENCE_MS // FRAME_MS


def list_input_devices() -> list[dict]:
    devices = sd.query_devices()
    default_idx = sd.default.device[0]
    return [
        {"id": str(idx), "name": d["name"], "is_default": idx == default_idx}
        for idx, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]


class AudioRecorder:
    """Push-to-talk style recorder: call start(), speak, call stop() to get audio.

    Also supports record_until_silence() for hands-free VAD-terminated capture.
    """

    def __init__(self, device: str | None = None, vad_aggressiveness: int = 2) -> None:
        self._device = int(device) if device is not None else None
        self._vad = webrtcvad.Vad(vad_aggressiveness)
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        self._frames = []

        def callback(indata, frames, time_info, status):  # noqa: ANN001
            if status:
                logger.warning("audio stream status: %s", status)
            self._frames.append(indata.copy())

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
        trailing_silent = 0
        last_voiced_frame = n_frames
        for i in range(n_frames):
            frame = pcm16[i * FRAME_SAMPLES : (i + 1) * FRAME_SAMPLES].tobytes()
            is_speech = self._vad.is_speech(frame, SAMPLE_RATE)
            if is_speech:
                trailing_silent = 0
                last_voiced_frame = i + 1
            else:
                trailing_silent += 1
        cutoff = min(last_voiced_frame + TRAILING_SILENCE_FRAMES, n_frames)
        return audio[: cutoff * FRAME_SAMPLES]
