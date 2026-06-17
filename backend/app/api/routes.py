from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app import config as cfg
from app.audio import list_input_devices
from app.pipeline import get_pipeline, history
from app.schemas import ConfigIn, ConfigOut, DeviceOut, HistoryEntry, ModelOut
from app.stt.engine import MODEL_CATALOG

router = APIRouter(prefix="/api")


@router.get("/config", response_model=ConfigOut)
def get_config() -> ConfigOut:
    s = cfg.load_settings()
    return ConfigOut(
        **s.model_dump(),
        gemini_api_key_set=cfg.has_gemini_api_key(),
    )


@router.put("/config", response_model=ConfigOut)
def update_config(body: ConfigIn) -> ConfigOut:
    s = cfg.load_settings()
    if body.hotkey is not None:
        s.hotkey = body.hotkey
    if body.mic_device is not None:
        s.mic_device = body.mic_device
    if body.stt_model is not None:
        s.stt_model = body.stt_model
    if body.stt_device is not None:
        s.stt_device = body.stt_device
    if body.language is not None:
        s.language = body.language
    if body.gemini_model is not None:
        s.gemini_model = body.gemini_model
    cfg.save_settings(s)

    if body.gemini_api_key is not None:
        cfg.set_gemini_api_key(body.gemini_api_key)

    if body.stt_model is not None or body.stt_device is not None:
        get_pipeline().reload_stt()

    return ConfigOut(**s.model_dump(), gemini_api_key_set=cfg.has_gemini_api_key())


@router.get("/devices", response_model=list[DeviceOut])
def get_devices() -> list[DeviceOut]:
    return [DeviceOut(**d) for d in list_input_devices()]


@router.get("/models", response_model=list[ModelOut])
def get_models() -> list[ModelOut]:
    labels = {
        "tiny": "Tiny (~75 MB) — fastest, lower accuracy",
        "base": "Base (~145 MB) — good balance (default)",
        "small": "Small (~480 MB) — better accuracy",
        "medium": "Medium (~1.5 GB) — high accuracy",
        "large": "Large (~2.9 GB) — best accuracy, slowest",
    }
    return [
        ModelOut(id=size, label=labels[size], approx_size_mb=mb)
        for size, mb in MODEL_CATALOG.items()
    ]


@router.get("/history", response_model=list[HistoryEntry])
def get_history() -> list[HistoryEntry]:
    return list(reversed(history))


@router.delete("/history", status_code=204)
def clear_history() -> None:
    history.clear()


@router.post("/dictate/start", status_code=202)
async def dictate_start() -> dict:
    await get_pipeline().start()
    return {"status": "recording"}


@router.post("/dictate/stop", status_code=202)
async def dictate_stop() -> dict:
    await get_pipeline().stop()
    return {"status": "processing"}
