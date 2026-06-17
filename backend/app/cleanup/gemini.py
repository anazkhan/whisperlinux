"""Gemini Flash based transcript cleanup.

Stateless: each call sends only the current raw transcript, no conversation
history, to keep latency and token usage minimal. On any failure (missing
key, network error, timeout, rate limit) the caller should fall back to the
raw transcript rather than blocking the dictation.
"""
from __future__ import annotations

import logging

from google import genai
from google.genai import errors as genai_errors

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You will receive a raw speech-to-text transcript that may contain filler "
    "words, false starts, or mis-transcribed words. Rewrite it as clean, "
    "well-formed text that reflects what the speaker intended to say. Output "
    "only the corrected text, with no preamble, quotes, or explanation."
)

DEFAULT_TIMEOUT_SECONDS = 5


class CleanupError(Exception):
    """Raised when the Gemini call fails; callers should fall back to raw text."""


class GeminiCleaner:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def clean(self, raw_text: str) -> str:
        if not raw_text.strip():
            return raw_text
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=raw_text,
                config={
                    "system_instruction": SYSTEM_PROMPT,
                    "temperature": 0.2,
                },
            )
        except genai_errors.APIError as exc:
            logger.warning("Gemini cleanup failed: %s", exc)
            raise CleanupError(str(exc)) from exc

        cleaned = (response.text or "").strip()
        return cleaned or raw_text
