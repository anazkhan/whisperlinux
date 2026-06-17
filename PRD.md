# WhisperLinux — Product Requirements Document

## 1. Summary

WhisperLinux is an open-source, system-wide voice dictation tool for Linux. A user
presses a hotkey, speaks, and the spoken words appear — as if typed on the keyboard —
in whatever application currently has focus (browser form, chat app, terminal, IDE,
anything that accepts keyboard input). Speech is transcribed locally with an
open-source speech-to-text model, then passed through Gemini Flash to clean up
disfluencies, filler words, and transcription errors so the final text reads as
intended, not as literally spoken.

The project ships as a local background service (system tray daemon) with a small
React-based local web UI used only for one-time setup and configuration (Gemini API
key, hotkey, microphone, model selection). There is no user account system — it is a
single-user local tool, and the UI has no authentication.

## 2. Problem Statement

Voice-to-text on Linux is fragmented: dictation tools are either tied to a specific
desktop environment, require a paid cloud service, or produce raw transcripts full of
"um"s, false starts, and mis-heard words that the user has to manually clean up before
the text is usable. There is no polished, open-source, cross-desktop tool that
combines fast local transcription with LLM-based cleanup and delivers the result
directly into the active application.

## 3. Goals

- Let a user dictate text into **any** focused application on Linux, not just a
  specific browser tab or app.
- Use a fast, fully open-source local STT model — no audio leaves the machine for
  transcription.
- Use Gemini Flash (via a user-supplied API key) to turn the raw transcript into clean,
  well-formed text that reflects what the user meant to say.
- Inject the final text via simulated keystrokes so it lands directly in the focused
  field, with no clipboard side effects.
- Keep end-to-end latency (end of speech → text appears) as low as practically
  possible.
- Ship as an open-source project anyone can clone, run locally, and contribute to.
- Zero-auth local setup: the only "credential" in the system is the user's own Gemini
  API key, entered once in the UI and stored locally.

## 4. Non-Goals (v1)

- No multi-user support, accounts, or remote/hosted deployment.
- No support for non-Linux platforms (macOS/Windows are out of scope for v1).
- No guarantee of full feature parity on Wayland compositors that restrict global
  input listening (see §9 Risks) — supported with a documented workaround.
- No bundled/local LLM cleanup fallback in v1 (Gemini Flash only); offline cleanup is
  a future extension.
- No telemetry, analytics, or phone-home behavior of any kind.

## 5. Target Users

- Linux desktop users who want hands-free text input across apps (accessibility,
  RSI/repetitive strain considerations, faster note-taking, chat-heavy workflows).
- Developers and power users comfortable running a local Python/Node service and
  pasting an API key into a settings page.
- Open-source contributors interested in STT, LLM tooling, or Linux desktop
  integration.

## 6. User Stories

1. As a user, I install WhisperLinux, open the local UI, paste my Gemini API key, pick
   a microphone, and set a hotkey — onboarding is done in under two minutes.
2. As a user, I'm typing a message in a browser chat box, I hold/press my configured
   hotkey, speak a sentence with a few "um"s and corrections, release the hotkey, and
   the clean final sentence is typed into the chat box automatically.
3. As a user, I switch focus to a terminal and dictate a long-form note; the text
   appears in the terminal exactly where my cursor was.
4. As a user, I want to see whether I'm currently recording, transcribing, or idle, via
   a tray icon indicator, without needing to keep the web UI open.
5. As a user, I want to choose a smaller/faster STT model on a low-power laptop, or a
   larger/more accurate model on a desktop with a GPU.
6. As a contributor, I want a documented architecture so I can add a new injection
   backend or STT engine without reading the whole codebase.

## 7. Functional Requirements

### 7.1 Audio Capture & Activation
- Global hotkey starts/stops recording from anywhere on the desktop, handled by a
  background tray application (see architecture.md for the X11/Wayland approach).
- Manual start/stop also available from the web UI as a fallback/status view.
- Voice activity detection (VAD) to auto-trim trailing silence and keep latency down.
- Microphone device selection in the UI.

### 7.2 Speech-to-Text
- Local, open-source STT engine (faster-whisper) transcribes captured audio.
- User can choose model size (tiny/base/small/medium/large) trading off speed vs.
  accuracy, and CPU vs. GPU execution if available.
- Language selection (default auto-detect or English).

### 7.3 Text Cleanup (Gemini Flash)
- Raw transcript is sent to Gemini Flash with a cleanup prompt that: removes filler
  words/false starts, fixes likely mis-transcriptions, infers intended meaning, and
  returns only the cleaned text (no commentary, no quotes).
- Gemini API key is supplied by the user via the UI and stored locally only.
- If the Gemini call fails (no network, bad key, rate limit), the system falls back to
  the raw transcript and clearly flags in the UI/tray that cleanup was skipped.

### 7.4 Text Injection
- Final cleaned text is delivered into the currently focused field via simulated
  keystrokes (not clipboard paste) — the text appears as if typed live.
- Works across X11 and Wayland via session-appropriate backends.

### 7.5 Settings & Local Web UI (React)
- First-run setup screen to paste/save the Gemini API key.
- Hotkey configuration.
- Microphone and STT model selection.
- Live status (idle / recording / transcribing / cleaning up / done / error).
- Recent dictation history (local only, clearable) for review/debugging.
- No login, no user accounts — UI is reachable only on localhost.

### 7.6 Packaging & Distribution
- FastAPI backend + tray daemon distributable as a pip-installable package and/or
  AppImage.
- React UI built and served by the backend (single local origin).
- Open-source license (MIT recommended) with CONTRIBUTING guide.

## 8. Non-Functional Requirements

- **Latency**: target under ~1.5–2s from end-of-speech to text appearing, for short
  utterances (≤10s), on a mid-range CPU. GPU acceleration should reduce this further.
- **Privacy**: audio and raw transcripts never leave the machine except the final
  transcript text sent to Gemini for cleanup. API key stored locally (OS keyring
  preferred over plaintext file).
- **Resource usage**: idle daemon footprint should be small; STT model loaded once at
  startup, not per-request, to avoid reload latency.
- **Portability**: must work on at least the major desktop environments (GNOME, KDE)
  across both X11 and Wayland sessions, with documented setup differences.
- **Reliability**: a failed Gemini call must never lose the user's dictated text (raw
  transcript fallback).

## 9. Risks & Open Questions

- **Wayland global hotkeys**: Wayland's security model blocks apps from grabbing
  global hotkeys directly. Mitigation: the daemon exposes a local trigger (CLI command
  / Unix socket) that the user binds to a custom shortcut in their desktop
  environment's own keyboard settings. This is documented as the supported path on
  Wayland; X11 can use direct hotkey registration.
- **Text injection permissions**: `ydotool` requires `uinput` device access
  (typically a group membership / udev rule) on Wayland; `xdotool` works out of the
  box on X11. Setup docs must cover this.
- **STT accuracy vs. latency tradeoff**: smaller models are faster but less accurate,
  particularly with accents/background noise — exposed as a user-facing setting rather
  than a fixed choice.
- **Gemini API cost/quota**: usage is billed to the user's own API key; no usage caps
  are enforced by WhisperLinux itself in v1.

## 10. Success Metrics

- End-to-end latency consistently under target on reference hardware (documented
  benchmark in repo).
- Successful dictation + injection across at least: a browser text field, a native
  GTK/Qt app, and a terminal.
- Onboarding (clone → first successful dictation) achievable in under 10 minutes
  following the README.
- Community adoption signals appropriate for an open-source project (issues, PRs,
  stars) — not a hard metric, but a directional goal.

## 11. Roadmap (indicative)

- **v0.1 (MVP)**: tray daemon, X11 global hotkey, faster-whisper (base model), Gemini
  Flash cleanup, xdotool injection, minimal React settings UI (API key + hotkey + mic).
- **v0.2**: Wayland support (ydotool + socket-trigger hotkey workaround), model
  picker, dictation history view, VAD tuning.
- **v1.0**: packaged AppImage/pip release, full docs, contributor guide, benchmark
  suite.
- **Future**: offline LLM cleanup fallback, additional injection backends (AT-SPI),
  streaming partial transcripts, multi-language UI.
  
  
  
  
  
  
  claude --resume fedf8909-591d-4e14-ac52-023bebd7824a

