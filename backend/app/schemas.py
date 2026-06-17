from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.config import ModelSize


class ConfigOut(BaseModel):
    hotkey: str
    mic_device: str | None
    stt_model: ModelSize
    stt_device: str
    language: str | None
    gemini_model: str
    gemini_api_key_set: bool


class ConfigIn(BaseModel):
    hotkey: str | None = None
    mic_device: str | None = None
    stt_model: ModelSize | None = None
    stt_device: str | None = None
    language: str | None = None
    gemini_model: str | None = None
    gemini_api_key: str | None = None


class DeviceOut(BaseModel):
    id: str
    name: str
    is_default: bool


class ModelOut(BaseModel):
    id: ModelSize
    label: str
    approx_size_mb: int


class HistoryEntry(BaseModel):
    timestamp: datetime
    raw_text: str
    cleaned_text: str
    cleanup_skipped: bool


class StatusEvent(BaseModel):
    state: str  # idle | recording | transcribing | cleaning_up | injecting | done | error
    detail: str | None = None
    entry: HistoryEntry | None = None
