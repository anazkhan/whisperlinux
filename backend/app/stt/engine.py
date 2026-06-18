"""Local speech-to-text via faster-whisper.

The model is loaded once and kept warm for the lifetime of the process to
avoid paying model-load latency on every dictation.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
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

# Models pre-downloaded by install.sh live here so no HF network calls at runtime.
_MODELS_DIR = Path(__file__).parent.parent.parent / "models"

HF_REPO: dict[ModelSize, str] = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large": "Systran/faster-whisper-large-v3",
}


def _model_path(model_size: ModelSize) -> str:
    """Return local path if pre-downloaded, else the HF model id (triggers download)."""
    local = _MODELS_DIR / model_size
    if local.exists() and any(local.iterdir()):
        return str(local)
    return HF_REPO[model_size]


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
        path = _model_path(self._model_size)
        logger.info("Loading faster-whisper model=%s device=%s source=%s", self._model_size, device, path)
        self._model = WhisperModel(path, device=device, compute_type=compute_type, local_files_only=Path(path).is_absolute())

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
            beam_size=1,
            condition_on_previous_text=False,
        )
        return "".join(segment.text for segment in segments).strip()
