# WhisperLinux — Architecture

## 1. Overview

WhisperLinux runs entirely on the user's machine as three cooperating pieces:

1. **Tray daemon** — a small always-running background process that owns the global
   hotkey trigger, microphone capture, and text injection (the parts that need direct
   OS/desktop access).
2. **FastAPI backend** — local HTTP/WebSocket server (bound to `127.0.0.1`) that hosts
   the STT engine, the Gemini Flash cleanup client, configuration storage, and serves
   the built React UI.
3. **React UI** — a local-only, no-auth settings and status app, served by the FastAPI
   backend and opened in the user's browser (or an embedded webview from the tray
   icon).

The tray daemon and FastAPI backend communicate over a local Unix domain socket or
loopback HTTP — they may run as a single process for simplicity in v1 (see §7).

```
                         ┌─────────────────────────────┐
                         │         React UI (SPA)       │
                         │  settings / status / history │
                         └───────────────┬───────────────┘
                                          │ HTTP + WebSocket (127.0.0.1)
                                          ▼
┌────────────────────────────────────────────────────────────────────┐
│                          FastAPI Backend                            │
│                                                                      │
│  ┌───────────────┐   ┌────────────────┐   ┌────────────────────┐   │
│  │ Config Store  │   │  STT Engine     │   │ Gemini Flash Client│   │
│  │ (api key,     │   │ (faster-whisper)│   │ (cleanup prompt)   │   │
│  │  hotkey, mic) │   └────────┬────────┘   └──────────┬─────────┘   │
│  └───────────────┘            │                       │             │
│                                ▼                       ▼             │
│                         Pipeline Orchestrator (async)               │
│                                │                                     │
└────────────────────────────────┼─────────────────────────────────────┘
                                  │ local socket / in-process call
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│                          Tray Daemon                                 │
│  ┌───────────────┐   ┌────────────────┐   ┌────────────────────┐    │
│  │ Hotkey Trigger│   │ Audio Recorder  │   │  Text Injector     │    │
│  │ (X11 direct / │   │ (sounddevice +  │   │ (xdotool / ydotool │    │
│  │  socket on    │   │  VAD)           │   │  / wtype)          │    │
│  │  Wayland)     │   └────────────────┘   └────────────────────┘    │
│  └───────────────┘                                                   │
└────────────────────────────────────────────────────────────────────┘
                │                                          ▲
                ▼                                          │
         Microphone (OS)                         Focused application
                                                  (keystrokes injected)
```

## 2. End-to-End Data Flow

1. User presses the configured hotkey (or clicks "Record" in the UI).
2. **Hotkey Trigger** notifies the **Audio Recorder** to start capturing from the
   selected microphone.
3. User speaks; **VAD** detects trailing silence (or user releases/re-presses the
   hotkey) to mark end of utterance.
4. Captured audio buffer is handed to the **STT Engine** (faster-whisper), which
   transcribes it locally and returns raw text.
5. Raw text is sent to the **Gemini Flash Client**, which calls the Gemini API with a
   cleanup prompt (system instruction: fix transcription errors, strip filler
   words/false starts, infer intended meaning, return only the cleaned sentence).
6. Cleaned text comes back; if the Gemini call fails, the raw transcript is used
   instead and the UI/tray status reflects "cleanup skipped."
7. The final text is passed to the **Text Injector**, which simulates keystrokes into
   whatever application currently holds focus.
8. The dictation (raw + cleaned text, timestamp) is appended to local history and
   pushed to the UI over WebSocket if it's open.

Status transitions broadcast to the UI at each step: `idle → recording →
transcribing → cleaning_up → injecting → done` (or `error` at any stage).

## 3. Technology Stack

| Layer                  | Choice                                   | Notes |
|------------------------|-------------------------------------------|-------|
| Backend framework      | FastAPI (Python, async)                  | REST + WebSocket, serves built React assets |
| STT engine             | faster-whisper (CTranslate2)             | CPU int8 by default, CUDA if available |
| VAD                    | webrtcvad or silero-vad                  | Trims silence, speeds up STT input |
| LLM cleanup            | Gemini Flash via `google-genai` SDK/REST | User-supplied API key |
| Audio capture          | `sounddevice` (PortAudio bindings)       | Cross-DE microphone access |
| Hotkey (X11)           | `python-xlib` / `pynput`                 | Direct global hotkey grab |
| Hotkey (Wayland)       | Desktop-bound custom shortcut → local CLI/socket trigger | See §5 |
| Text injection (X11)   | `xdotool`                                 | Simulated keystrokes |
| Text injection (Wayland)| `ydotool` (uinput) or `wtype`            | Requires uinput permissions |
| Frontend               | React (Vite), no auth                    | Settings, status, history |
| Config storage          | Local JSON + OS keyring for the API key  | `~/.config/whisperlinux/` |
| Tray icon               | `pystray` or native AppIndicator binding | Status indicator, quick toggle |
| Packaging               | pip package + AppImage                   | systemd user service optional, for autostart |

## 4. Backend API Design

All endpoints are bound to `127.0.0.1` only; no authentication layer (single local
user, explicitly out of scope per PRD).

### REST
- `GET /api/config` — current settings (hotkey, mic device, STT model, language).
  API key is never returned in full, only a masked indicator of whether it's set.
- `PUT /api/config` — update settings, including the Gemini API key (stored via
  keyring, not echoed back).
- `GET /api/devices` — list available microphone input devices.
- `GET /api/models` — list available local STT models/sizes and current selection.
- `GET /api/history` — recent dictations (raw + cleaned text, timestamp).
- `DELETE /api/history` — clear local history.
- `POST /api/dictate/start` / `POST /api/dictate/stop` — manual control from the UI
  (mirrors what the hotkey trigger does).

### WebSocket
- `WS /ws/status` — pushes pipeline state changes (`idle`, `recording`,
  `transcribing`, `cleaning_up`, `injecting`, `done`, `error`) and final
  raw/cleaned text for each dictation, so the UI updates live without polling.

## 5. Hotkey & Injection: X11 vs Wayland

This is the trickiest portability issue and is called out explicitly:

- **X11**: the tray daemon can register a global hotkey directly (via `python-xlib`/
  `pynput`) and inject keystrokes directly via `xdotool`. No extra user setup beyond
  installing `xdotool`.
- **Wayland**: compositors intentionally block apps from grabbing global hotkeys for
  security reasons. WhisperLinux's daemon instead exposes a small CLI command
  (e.g. `whisperlinux-toggle`) that talks to the running daemon over a Unix domain
  socket. The user binds this command to a custom keyboard shortcut in their desktop
  environment's own settings (GNOME Settings → Keyboard Shortcuts, KDE System
  Settings, etc.) — this is the documented, supported activation path on Wayland.
  Text injection uses `ydotool` (which requires the user to be in the group with
  `uinput` access, set up via a one-time udev rule documented in the README) or
  `wtype` as a lighter alternative on wlroots-based compositors.
- At startup, the daemon detects `XDG_SESSION_TYPE` and selects the appropriate
  hotkey/injection backend automatically, falling back to the socket+CLI flow if
  direct hotkey grabbing isn't available.

## 6. Gemini Flash Cleanup

- Client uses the official `google-genai` Python SDK (or plain REST) with the user's
  API key, calling a Flash-tier model (configurable model name, defaulting to the
  latest available Gemini Flash model).
- System prompt is fixed and minimal, e.g.:
  > "You will receive a raw speech-to-text transcript that may contain filler words,
  > false starts, or mis-transcribed words. Rewrite it as clean, well-formed text that
  > reflects what the speaker intended to say. Output only the corrected text, with no
  > preamble, quotes, or explanation."
- Calls are made with a short timeout; on timeout/error/missing key, the pipeline
  degrades gracefully to the raw transcript (per PRD §7.3).
- No conversation/history is sent to Gemini — each cleanup call is stateless and
  contains only the current transcript, to minimize latency and token usage.

## 7. Process Model

- v1 ships the tray daemon and FastAPI backend as a single Python process for
  simplicity (one `asyncio` event loop, hotkey/audio callbacks scheduled onto it).
- The tray icon (via `pystray`) runs in this same process and reflects pipeline state.
- This avoids IPC complexity for v1; the socket/CLI trigger described in §5 is still
  exposed externally (for the Wayland shortcut binding) even though internally it's
  just a function call within the same process.
- A future split into a slim always-on daemon + on-demand backend is possible but not
  required for v1 (see PRD roadmap).

## 8. Performance / Latency Engineering

- STT model is loaded once at process startup (not per-request) to avoid reload cost
  on every dictation.
- VAD trims silence before/after speech so the STT engine only processes the actual
  utterance.
- faster-whisper runs with int8 quantization on CPU by default; GPU (CUDA) path used
  automatically if detected.
- Gemini Flash call uses a persistent HTTP client/connection pool (no per-call TLS
  handshake).
- Pipeline stages (STT → Gemini → injection) run as sequential async steps within one
  request lifecycle; no unnecessary buffering or extra hops.
- Target latency budget for a short (~5–10s) utterance:
  - VAD tail trim: ~150–300ms
  - STT (base/small model, CPU int8): ~200–500ms
  - Gemini Flash round-trip: ~300–800ms
  - Keystroke injection: ~50–150ms (scales with text length)
  - **Total**: roughly 1–1.5s on typical hardware; documented as a benchmark target,
    not a hard guarantee, since it depends on hardware and network conditions.

## 9. Security & Privacy

- Backend binds to `127.0.0.1` only — never exposed on the network.
- Gemini API key stored via the OS keyring where available; falls back to a local
  config file with restrictive permissions (`chmod 600`) if no keyring is present.
  Never logged, never included in history exports.
- Audio and raw transcripts stay local; only the final transcript text is sent to
  Google's Gemini API over HTTPS, using the user's own key.
- No telemetry, analytics, or external calls other than the explicit Gemini cleanup
  request.

## 10. Repository Layout

```
whisperlinux/
├── backend/                 # FastAPI app, STT, Gemini client, daemon, injection
│   ├── app/
│   │   ├── api/             # REST + WebSocket routes
│   │   ├── stt/             # faster-whisper wrapper
│   │   ├── cleanup/         # Gemini Flash client + prompt
│   │   ├── injection/       # xdotool/ydotool/wtype backends
│   │   ├── hotkey/          # X11 direct + Wayland socket trigger
│   │   ├── config.py        # settings + keyring storage
│   │   └── main.py
│   └── pyproject.toml
├── frontend/                # React (Vite) settings/status UI
│   ├── src/
│   └── package.json
├── packaging/                # AppImage spec, systemd unit, udev rule for uinput
├── docs/                      # PRD.md, architecture.md, setup guides per DE
├── PRD.md
├── architecture.md
└── README.md
```

## 11. Testing Strategy

- Unit tests for the cleanup prompt/response parsing (mocked Gemini responses).
- Unit tests for config storage (keyring fallback behavior).
- Integration tests that feed a pre-recorded WAV file through STT → cleanup → mocked
  injector, asserting the full pipeline and status transitions.
- Manual/documented test matrix across GNOME (Wayland), KDE (Wayland), and an X11
  session, since hotkey/injection behavior is environment-dependent and hard to fully
  automate in CI.

## 12. Future Extensions

- Offline LLM cleanup fallback (e.g. local small model) for when no API key/network
  is available.
- Streaming partial transcripts for visual feedback while still speaking.
- Additional injection backend via AT-SPI for apps where keystroke simulation is
  unreliable.
- Multi-language UI and STT language auto-switching.
- Optional packaged Flatpak for sandboxed distribution.
