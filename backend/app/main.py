"""WhisperLinux — FastAPI application entry point.

Starts the FastAPI server, loads the STT model, registers the hotkey trigger,
and launches the system tray icon, all in a single process.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.api.ws import broadcast_loop, router as ws_router
from app.config import load_settings
from app.hotkey.factory import get_trigger
from app.pipeline import get_pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"
HOST = "127.0.0.1"
PORT = 7777


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    # Warm the STT model before accepting requests.
    pipeline = get_pipeline()

    # Start the WebSocket broadcaster.
    broadcaster = asyncio.create_task(broadcast_loop())

    # Register the global hotkey trigger.
    settings = load_settings()
    trigger = get_trigger(settings.hotkey)
    loop = asyncio.get_running_loop()

    def on_toggle() -> None:
        asyncio.run_coroutine_threadsafe(pipeline.toggle(), loop)

    trigger.start(on_toggle)
    logger.info("Hotkey trigger started")

    yield

    trigger.stop()
    broadcaster.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title="WhisperLinux", version="0.1.0", lifespan=lifespan)
    app.include_router(api_router)
    app.include_router(ws_router)

    # Serve the built React UI if the dist folder exists.
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="ui")

    return app


app = create_app()


def run() -> None:
    logger.info("WhisperLinux running at http://%s:%d", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    run()
