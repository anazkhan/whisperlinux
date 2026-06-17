"""Global hotkey registration on X11 via pynput.

pynput's GlobalHotKeys parses strings like '<ctrl>+<alt>+space', which
matches the format stored in Settings.hotkey, so no translation needed.
"""
from __future__ import annotations

import logging

from pynput import keyboard

from app.hotkey.base import HotkeyTrigger, ToggleCallback

logger = logging.getLogger(__name__)


class X11HotkeyTrigger(HotkeyTrigger):
    def __init__(self, hotkey: str) -> None:
        self._hotkey = hotkey
        self._listener: keyboard.GlobalHotKeys | None = None

    def start(self, on_toggle: ToggleCallback) -> None:
        def _on_activate() -> None:
            logger.debug("hotkey activated")
            on_toggle()

        self._listener = keyboard.GlobalHotKeys({self._hotkey: _on_activate})
        self._listener.start()
        logger.info("X11 global hotkey registered: %s", self._hotkey)

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
