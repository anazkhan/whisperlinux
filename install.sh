#!/usr/bin/env bash
# WhisperLinux installer
# Usage: bash install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$REPO_DIR/backend"
FRONTEND_DIR="$REPO_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"

# ── Colours ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}▸ $*${RESET}"; }
success() { echo -e "${GREEN}✓ $*${RESET}"; }
warn()    { echo -e "${YELLOW}⚠ $*${RESET}"; }
error()   { echo -e "${RED}✗ $*${RESET}" >&2; exit 1; }
header()  { echo -e "\n${BOLD}$*${RESET}"; }

# ── 1. Python ──────────────────────────────────────────────────────────────────
header "Checking Python..."
PYTHON=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &>/dev/null; then
        VERSION=$("$candidate" -c 'import sys; print(sys.version_info[:2])')
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'; then
            PYTHON="$candidate"
            break
        fi
    fi
done
[ -z "$PYTHON" ] && error "Python 3.10+ is required. Install it and retry."
success "Found $($PYTHON --version)"

# ── 2. Node / npm ──────────────────────────────────────────────────────────────
header "Checking Node.js..."
if ! command -v node &>/dev/null; then
    error "Node.js 18+ is required. Install it from https://nodejs.org and retry."
fi
NODE_MAJOR=$(node -e "process.stdout.write(process.versions.node.split('.')[0])")
if [ "$NODE_MAJOR" -lt 18 ]; then
    error "Node.js 18+ required, found $(node --version). Please upgrade."
fi
success "Found $(node --version)"

# ── 3. System dependencies ─────────────────────────────────────────────────────
header "Installing system dependencies..."
SESSION="${XDG_SESSION_TYPE:-unknown}"
info "Session type: $SESSION"

install_pkg() {
    local pkg="$1"
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y "$pkg"
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y "$pkg"
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm "$pkg"
    elif command -v zypper &>/dev/null; then
        sudo zypper install -y "$pkg"
    else
        warn "Could not auto-install $pkg — please install it manually then re-run."
        return 1
    fi
}

# PortAudio — required by sounddevice (microphone capture)
if ! ldconfig -p 2>/dev/null | grep -q libportaudio; then
    info "Installing PortAudio (required for microphone access)..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y libportaudio2 portaudio19-dev
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y portaudio portaudio-devel
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm portaudio
    elif command -v zypper &>/dev/null; then
        sudo zypper install -y portaudio-devel
    else
        warn "Please install PortAudio manually (libportaudio2) then re-run."
    fi
    success "PortAudio installed"
else
    success "PortAudio already available"
fi

# Text injection tool — xdotool (X11) or ydotool (Wayland)
if [ "$SESSION" = "wayland" ]; then
    if ! command -v ydotool &>/dev/null; then
        info "Wayland session — installing ydotool..."
        install_pkg ydotool || warn "ydotool not installed. Text injection will not work until you install it."
    else
        success "ydotool found"
    fi
    info "Setting up uinput access for ydotool..."
    if [ -f "$REPO_DIR/packaging/udev/60-whisperlinux-uinput.rules" ]; then
        sudo cp "$REPO_DIR/packaging/udev/60-whisperlinux-uinput.rules" /etc/udev/rules.d/
        sudo udevadm control --reload-rules
        sudo udevadm trigger
        sudo usermod -aG input "$USER"
        warn "You must log out and back in for the uinput group change to take effect."
    fi
else
    # X11 or unknown — use xdotool
    if ! command -v xdotool &>/dev/null; then
        info "X11 session — installing xdotool..."
        install_pkg xdotool || warn "xdotool not installed. Text injection will not work until you install it."
    else
        success "xdotool found"
    fi
fi

# ── 4. Python venv + backend ───────────────────────────────────────────────────
header "Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    info "Creating venv at $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
fi
VENV_PIP="$VENV_DIR/bin/pip"
VENV_PYTHON="$VENV_DIR/bin/python"
info "Upgrading pip..."
"$VENV_PIP" install --quiet --upgrade pip
info "Installing WhisperLinux backend..."
"$VENV_PIP" install --quiet -e "$BACKEND_DIR"
success "Backend installed"

# ── 5. Frontend build ──────────────────────────────────────────────────────────
header "Building frontend..."
cd "$FRONTEND_DIR"
info "Installing Node dependencies..."
npm install --silent
info "Building React UI..."
npm run build --silent
success "Frontend built"

# ── 6. Optional systemd autostart ─────────────────────────────────────────────
header "Autostart (optional)..."
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_SRC="$REPO_DIR/packaging/systemd/whisperlinux.service"
SERVICE_DEST="$SYSTEMD_USER_DIR/whisperlinux.service"

if systemctl --user is-active --quiet whisperlinux 2>/dev/null; then
    success "systemd service already running"
elif command -v systemctl &>/dev/null; then
    read -r -p "$(echo -e "${YELLOW}Enable WhisperLinux to start automatically on login? [y/N]: ${RESET}")" AUTOSTART
    if [[ "$AUTOSTART" =~ ^[Yy]$ ]]; then
        mkdir -p "$SYSTEMD_USER_DIR"
        # Write service file with the correct venv path baked in
        sed "s|ExecStart=.*|ExecStart=$VENV_DIR/bin/whisperlinux|" "$SERVICE_SRC" > "$SERVICE_DEST"
        systemctl --user daemon-reload
        systemctl --user enable --now whisperlinux
        success "Service enabled and started"
    else
        info "Skipped autostart"
    fi
fi

# ── Done ───────────────────────────────────────────────────────────────────────
WHISPERLINUX_BIN="$VENV_DIR/bin/whisperlinux"

echo ""
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}${BOLD}  WhisperLinux is ready!${RESET}"
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  Run it anytime with:"
echo -e "  ${CYAN}${BOLD}$WHISPERLINUX_BIN${RESET}"
echo ""
echo -e "  Then open ${CYAN}http://localhost:7777${RESET} to:"
echo -e "  1. Paste your Gemini API key"
echo -e "  2. Pick your microphone"
echo -e "  3. Set your hotkey (default: Ctrl+Alt+Space)"
echo -e "  4. Click Save — then start dictating into any app"
echo ""

if [ "$SESSION" = "wayland" ]; then
    echo -e "${YELLOW}  Wayland hotkey setup:${RESET}"
    echo -e "  Bind ${CYAN}whisperlinux-toggle${RESET} to a shortcut in your DE settings."
    echo -e "  GNOME: Settings → Keyboard → Custom Shortcuts"
    echo -e "  KDE:   System Settings → Shortcuts → Custom Shortcuts"
    echo ""
fi
