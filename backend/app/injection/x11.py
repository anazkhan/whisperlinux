from __future__ import annotations

import subprocess

from app.injection.base import TextInjector


class XdotoolInjector(TextInjector):
    """Types into the focused window via xdotool (X11 only)."""

    def type_text(self, text: str) -> None:
        if not text:
            return
        subprocess.run(
            ["xdotool", "type", "--clearmodifiers", "--delay", "0", "--", text],
            check=True,
        )
