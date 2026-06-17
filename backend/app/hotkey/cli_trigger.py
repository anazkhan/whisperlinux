"""Entry point for the `whisperlinux-toggle` console command.

Bind this command to a keyboard shortcut in GNOME/KDE/etc. settings to get
a global hotkey on Wayland without any compositor-level access.

Usage:
    whisperlinux-toggle
"""
from __future__ import annotations

import sys


def main() -> None:
    try:
        from app.hotkey.socket_trigger import send_toggle

        send_toggle()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
