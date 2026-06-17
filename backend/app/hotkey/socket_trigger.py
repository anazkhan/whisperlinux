"""Unix domain socket trigger — the Wayland-friendly hotkey path.

The daemon listens on a socket; the `whisperlinux-toggle` CLI connects and
sends "toggle\n". The user binds that CLI command to a custom keyboard
shortcut in their desktop environment settings (GNOME/KDE), which works
without any compositor-level global hotkey access.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from app.hotkey.base import HotkeyTrigger, ToggleCallback

logger = logging.getLogger(__name__)

SOCKET_PATH = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "whisperlinux.sock"
_MSG = b"toggle\n"


class SocketHotkeyTrigger(HotkeyTrigger):
    """Asyncio-based socket listener — must be started from within a running loop."""

    def __init__(self) -> None:
        self._server: asyncio.AbstractServer | None = None
        self._on_toggle: ToggleCallback | None = None

    async def _handle(self, reader: asyncio.StreamReader, _writer: asyncio.StreamWriter) -> None:
        data = await reader.read(64)
        if data.strip() == b"toggle":
            logger.debug("socket trigger received toggle")
            if self._on_toggle:
                self._on_toggle()

    def start(self, on_toggle: ToggleCallback) -> None:
        self._on_toggle = on_toggle
        asyncio.get_event_loop().create_task(self._serve())

    async def _serve(self) -> None:
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
        self._server = await asyncio.start_unix_server(self._handle, path=str(SOCKET_PATH))
        logger.info("socket trigger listening at %s", SOCKET_PATH)
        async with self._server:
            await self._server.serve_forever()

    def stop(self) -> None:
        if self._server is not None:
            self._server.close()
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink(missing_ok=True)


def send_toggle() -> None:
    """Send a toggle message to the running daemon (synchronous, for the CLI)."""
    import socket

    if not SOCKET_PATH.exists():
        raise RuntimeError(
            f"WhisperLinux daemon socket not found at {SOCKET_PATH}. "
            "Is the daemon running?"
        )
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(SOCKET_PATH))
        sock.sendall(_MSG)
