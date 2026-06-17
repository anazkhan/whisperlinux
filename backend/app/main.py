"""WhisperLinux — FastAPI application entry point.

Starts the FastAPI server, loads the STT model, registers the hotkey trigger,
and launches the system tray icon, all in a single process.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import webbrowser
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

    def on_toggle() -> None:
        asyncio.run_coroutine_threadsafe(pipeline.toggle(), asyncio.get_event_loop())

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


def _run_tray() -> None:
    try:
        import pystray
        from PIL import Image, ImageDraw

        def _icon_image(color: str = "green") -> Image.Image:
            img = Image.new("RGB", (64, 64), color=(30, 30, 30))
            draw = ImageDraw.Draw(img)
            draw.ellipse([16, 16, 48, 48], fill=color)
            return img

        def open_ui(icon, item) -> None:  # noqa: ANN001
            webbrowser.open(f"http://{HOST}:{PORT}")

        def quit_app(icon, item) -> None:  # noqa: ANN001
            icon.stop()
            import os, signal
            os.kill(os.getpid(), signal.SIGTERM)

        menu = pystray.Menu(
            pystray.MenuItem("Open settings", open_ui, default=True),
            pystray.MenuItem("Quit", quit_app),
        )
        icon = pystray.Icon("whisperlinux", _icon_image(), "WhisperLinux", menu)
        icon.run()
    except Exception as exc:
        logger.warning("Tray icon unavailable: %s", exc)


def run() -> None:
    tray_thread = threading.Thread(target=_run_tray, daemon=True)
    tray_thread.start()

    logger.info("WhisperLinux running at http://%s:%d", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    run()
