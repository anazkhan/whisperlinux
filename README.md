# WhisperLinux

System-wide voice dictation for Linux. Press a hotkey, speak, and the text appears — typed directly into whatever app has focus — in under two seconds.

- **Local STT** via [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — audio never leaves your machine
- **LLM cleanup** via Gemini Flash — strips filler words, fixes transcription errors
- **Direct keystroke injection** — no clipboard side-effects, text lands exactly where your cursor is
- **Simple web UI** on `localhost:7777` — no accounts, no auth

---

## Requirements

Before running the installer, make sure you have:

- **Python 3.10+** — `python3 --version`
- **Node.js 18+** — `node --version` (get it from [nodejs.org](https://nodejs.org))
- **sudo access** — the installer needs it to install system audio libs and the injection tool
- **A Gemini API key** — free tier available at [aistudio.google.com](https://aistudio.google.com/app/apikey)

Everything else (xdotool, ydotool, PortAudio, Python venv, frontend build) is handled automatically by the installer.

---

## Install

```bash
git clone https://github.com/anazkhan/whisperlinux.git
cd whisperlinux
bash install.sh
```

The script will:
1. Install system dependencies — PortAudio (mic access) and the right injection tool for your session (`xdotool` on X11, `ydotool` on Wayland)
2. Create a Python virtual environment and install the backend
3. Build the React frontend
4. Ask if you want WhisperLinux to start automatically on login (systemd user service)

At the end it prints the exact command to launch the app.

---

## Start

```bash
backend/.venv/bin/whisperlinux
```

Then open **http://localhost:7777** in your browser and complete the one-time setup:

1. Paste your **Gemini API key**
2. Select your **microphone**
3. Pick a **model size** — Base is a good default (fast, decent accuracy)
4. Set your **hotkey** — default is `Ctrl+Q`
5. Click **Save settings**

That's it. From now on, press your hotkey in any app, speak, and the cleaned-up text is typed in for you.

---

## Hotkey on Wayland

Wayland doesn't allow apps to grab global hotkeys directly. The installer sets up a
`whisperlinux-toggle` command — bind it to a keyboard shortcut in your desktop settings:

- **GNOME:** Settings → Keyboard → Custom Shortcuts → `+` → Command: `whisperlinux-toggle`
- **KDE:** System Settings → Shortcuts → Custom Shortcuts → New → Command/URL: `whisperlinux-toggle`

---

## Autostart

The installer asks about this at the end. If you said no and want to enable it later:

```bash
bash install.sh   # re-run and say yes when prompted
```

Or manually:

```bash
mkdir -p ~/.config/systemd/user
sed "s|ExecStart=.*|ExecStart=$PWD/backend/.venv/bin/whisperlinux|" \
    packaging/systemd/whisperlinux.service \
    > ~/.config/systemd/user/whisperlinux.service
systemctl --user enable --now whisperlinux
```

---

## Development

```bash
# Terminal 1 — backend with auto-reload
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 7777

# Terminal 2 — frontend dev server (proxies /api and /ws to the backend)
cd frontend
npm run dev
```

Open **http://localhost:5173** for the hot-reloading UI during development.

---

## Project structure

```
whisperlinux/
├── backend/
│   ├── app/
│   │   ├── api/          # REST routes + WebSocket
│   │   ├── audio.py      # Microphone capture + VAD trim
│   │   ├── cleanup/      # Gemini Flash cleanup client
│   │   ├── config.py     # Settings + OS keyring storage
│   │   ├── hotkey/       # X11 direct grab + Wayland socket trigger
│   │   ├── injection/    # xdotool (X11) / ydotool / wtype (Wayland)
│   │   ├── pipeline.py   # Async orchestrator
│   │   ├── schemas.py    # Pydantic models
│   │   └── stt/          # faster-whisper wrapper
│   └── pyproject.toml
├── frontend/             # React + Vite settings UI
├── packaging/            # systemd unit, udev rule for Wayland
├── install.sh            # One-command installer
├── PRD.md
├── architecture.md
└── README.md
```

---

## Latency

Typical end-to-end time (end of speech → text appears) on a mid-range CPU:

| Stage | Time |
|---|---|
| VAD silence trim | ~150–300 ms |
| STT — base model, int8 CPU | ~200–500 ms |
| Gemini Flash API | ~300–800 ms |
| Keystroke injection | ~50–150 ms |
| **Total** | **~0.7–1.8 s** |

GPU (CUDA) cuts the STT step significantly. Choosing the `tiny` model reduces it further at some accuracy cost.

---

## Contributing

Pull requests welcome. See `architecture.md` for the full technical overview before making structural changes.

## License

MIT — see [LICENSE](LICENSE).
