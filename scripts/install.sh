#!/usr/bin/env bash
# Created: 2026-07-26
# Last Edited: 2026-07-26 11:07 CT (America/Chicago)
# Path: scripts/install.sh
# Purpose: Standalone installer for AetherPod — detects environment and
#          offers system-wide, user-level, or venv installation.

set -euo pipefail

cd "$(dirname "$0")/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}$*${NC}"; }
ok()    { echo -e "${GREEN}✓ $*${NC}"; }
err()   { echo -e "${RED}✗ $*${NC}" >&2; }

# Check Python availability
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    err "Python 3 not found. Install Python >= 3.9 first."
    exit 1
fi

PYVER=$("$PYTHON" --version 2>&1 | grep -oP '\d+\.\d+')
info "Detected: $("$PYTHON" --version)"

# Check if we're inside a venv
IN_VENV=false
if [ -n "${VIRTUAL_ENV:-}" ]; then
    IN_VENV=true
    info "Active venv: $VIRTUAL_ENV"
fi

echo ""
info "Choose installation method:"
echo "  1) System-wide  (requires pip's --break-system-packages or root)"
echo "  2) User-local   (installs to ~/.local, no root)"
echo "  3) New venv     (creates .venv/ in current directory)"
echo "  4) Current venv (uses the already-active venv — only available if a venv is active)"
echo ""

read -rp "Choice [1-4]: " choice

case "$choice" in
    1)
        info "Installing system-wide..."
        if command -v sudo &>/dev/null; then
            sudo "$PYTHON" -m pip install --break-system-packages -e .
        else
            "$PYTHON" -m pip install --break-system-packages -e .
        fi
        ok "Installed system-wide. Run: aetherpod"
        ;;
    2)
        info "Installing to ~/.local..."
        "$PYTHON" -m pip install --user -e .
        ok "Installed to ~/.local. Ensure ~/.local/bin is on your PATH."
        ;;
    3)
        VENV_DIR=".venv"
        info "Creating venv at $VENV_DIR ..."
        "$PYTHON" -m venv --prompt aetherpod "$VENV_DIR"
        # shellcheck disable=SC1091
        source "$VENV_DIR/bin/activate"
        pip install -e .
        ok "Installed in venv ($VENV_DIR)."
        echo "Activate it later with: source $VENV_DIR/bin/activate"
        ;;
    4)
        if [ "$IN_VENV" = false ]; then
            err "No venv is active. Activate one first or choose another option."
            exit 1
        fi
        info "Installing into active venv..."
        pip install -e .
        ok "Installed into active venv ($VIRTUAL_ENV)."
        ;;
    *)
        err "Invalid choice."
        exit 1
        ;;
esac

echo ""
info "Done! Run 'aetherpod --help' to get started."
