"""Local configuration storage.

Settings live in ~/.config/whisperlinux/config.json. The Gemini API key is
never written into that file: it is stored via the OS keyring when available,
falling back to a 0600-permission file alongside the config if no keyring
backend is present (e.g. minimal headless setups).
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

try:
    import keyring
    from keyring.errors import NoKeyringError
except ImportError:  # pragma: no cover - keyring is a hard dependency, but be defensive
    keyring = None
    NoKeyringError = Exception

CONFIG_DIR = Path(os.environ.get("WHISPERLINUX_CONFIG_DIR", Path.home() / ".config" / "whisperlinux"))
CONFIG_FILE = CONFIG_DIR / "config.json"
FALLBACK_KEY_FILE = CONFIG_DIR / "gemini.key"
KEYRING_SERVICE = "whisperlinux"
KEYRING_USERNAME = "gemini-api-key"

ModelSize = Literal["tiny", "base", "small", "medium", "large"]


class Settings(BaseModel):
    hotkey: str = "<ctrl>+<alt>+<space>"
    mic_device: str | None = None
    stt_model: ModelSize = "base"
    stt_device: Literal["auto", "cpu", "cuda"] = "auto"
    language: str | None = None  # None => auto-detect
    gemini_model: str = "gemini-2.0-flash"


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    if not CONFIG_FILE.exists():
        return Settings()
    data = json.loads(CONFIG_FILE.read_text())
    return Settings(**data)


def save_settings(settings: Settings) -> None:
    _ensure_config_dir()
    CONFIG_FILE.write_text(settings.model_dump_json(indent=2))


def get_gemini_api_key() -> str | None:
    if keyring is not None:
        try:
            value = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
            if value:
                return value
        except NoKeyringError:
            pass
    if FALLBACK_KEY_FILE.exists():
        return FALLBACK_KEY_FILE.read_text().strip() or None
    return None


def set_gemini_api_key(api_key: str) -> None:
    if keyring is not None:
        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, api_key)
            return
        except NoKeyringError:
            pass
    _ensure_config_dir()
    FALLBACK_KEY_FILE.write_text(api_key)
    FALLBACK_KEY_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)


def has_gemini_api_key() -> bool:
    return get_gemini_api_key() is not None
