"""Local speech-to-text via faster-whisper.

The model is loaded once and kept warm for the lifetime of the process to
avoid paying model-load latency on every dictation.
"""
from __future__ import annotations

import logging
from typing import Literal

import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

ModelSize = Literal["tiny", "base", "small", "medium", "large"]

MODEL_CATALOG: dict[ModelSize, int] = {
    "tiny": 75,
    "base": 145,
    "small": 480,
    "medium": 1500,
    "large": 2900,
}


class SttEngine:
    """Thin wrapper around a warm faster-whisper model instance."""

    def __init__(self, model_size: ModelSize = "base", device: str = "auto") -> None:
        self._model_size = model_size
        self._device = device
        self._model: WhisperModel | None = None
        self.load()

    def load(self) -> None:
        compute_type = "int8" if self._device in ("auto", "cpu") else "float16"
        device = "cpu" if self._device == "auto" else self._device
        logger.info("Loading faster-whisper model=%s device=%s", self._model_size, device)
        self._model = WhisperModel(self._model_size, device=device, compute_type=compute_type)

    def reload(self, model_size: ModelSize, device: str) -> None:
        if model_size == self._model_size and device == self._device:
            return
        self._model_size = model_size
        self._device = device
        self.load()

    def transcribe(self, audio: np.ndarray, language: str | None = None) -> str:
        """audio: mono float32 PCM at 16kHz."""
        assert self._model is not None
        segments, _info = self._model.transcribe(
            audio,
            language=language,
            vad_filter=False,  # VAD is already applied upstream during capture
            beam_size=5,
        )
        return "".join(segment.text for segment in segments).strip()
