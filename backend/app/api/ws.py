"""WebSocket endpoint — fans pipeline StatusEvents out to all connected UIs."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.pipeline import status_bus

router = APIRouter()
logger = logging.getLogger(__name__)

_clients: set[WebSocket] = set()


@router.websocket("/ws/status")
async def ws_status(websocket: WebSocket) -> None:
    await websocket.accept()
    _clients.add(websocket)
    try:
        # Keep the connection alive; rely on the broadcaster task to push events.
        while True:
            await asyncio.sleep(15)
            await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(websocket)


async def broadcast_loop() -> None:
    """Runs as a background task: drains status_bus and pushes to all clients."""
    while True:
        event = await status_bus.get()
        if not _clients:
            continue
        payload = event.model_dump_json()
        dead: set[WebSocket] = set()
        for ws in list(_clients):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        _clients -= dead
