from __future__ import annotations

import os
import shutil
from abc import ABC, abstractmethod


class TextInjector(ABC):
    @abstractmethod
    def type_text(self, text: str) -> None:
        """Simulate keystrokes for `text` into whatever currently has focus."""


class InjectionUnavailable(RuntimeError):
    pass


def get_injector() -> TextInjector:
    """Pick the right backend for the current session.

    X11 sessions use xdotool. Wayland sessions prefer ydotool, falling back
    to wtype if ydotool/uinput access isn't set up.
    """
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()

    if session_type == "x11":
        from app.injection.x11 import XdotoolInjector

        return XdotoolInjector()

    if session_type == "wayland":
        if shutil.which("ydotool"):
            from app.injection.wayland import YdotoolInjector

            return YdotoolInjector()
        if shutil.which("wtype"):
            from app.injection.wayland import WtypeInjector

            return WtypeInjector()
        raise InjectionUnavailable(
            "Wayland session detected but neither 'ydotool' nor 'wtype' is "
            "installed. See docs/setup-wayland.md."
        )

    # Unknown session type: best-effort, try xdotool first.
    if shutil.which("xdotool"):
        from app.injection.x11 import XdotoolInjector

        return XdotoolInjector()
    raise InjectionUnavailable(f"Unsupported or undetected session type: {session_type!r}")
