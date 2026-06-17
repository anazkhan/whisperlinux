from __future__ import annotations

import subprocess

from app.injection.base import TextInjector


class YdotoolInjector(TextInjector):
    """Types into the focused window via ydotool (requires uinput access).

    See packaging/udev/60-whisperlinux-uinput.rules for the one-time setup
    that grants the running user access to /dev/uinput without root.
    """

    def type_text(self, text: str) -> None:
        if not text:
            return
        subprocess.run(["ydotool", "type", "--", text], check=True)


class WtypeInjector(TextInjector):
    """Lighter-weight alternative for wlroots-based compositors."""

    def type_text(self, text: str) -> None:
        if not text:
            return
        subprocess.run(["wtype", text], check=True)
