"""Pick the right hotkey trigger for the current session."""
from __future__ import annotations

import os

from app.hotkey.base import HotkeyTrigger


def get_trigger(hotkey: str) -> HotkeyTrigger:
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()

    if session_type == "wayland":
        from app.hotkey.socket_trigger import SocketHotkeyTrigger
        return SocketHotkeyTrigger()

    # X11 or unknown: try direct global hotkey registration.
    from app.hotkey.x11 import X11HotkeyTrigger
    return X11HotkeyTrigger(hotkey)
