#!/usr/bin/env bash
#
# Render the launchd plists with absolute paths for this machine,
# install them into ~/Library/LaunchAgents, and load them.
#
# Idempotent — safe to re-run after edits to the templates.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOME_DIR="$HOME"
AGENTS_DIR="$HOME/Library/LaunchAgents"
LOGS_DIR="$HOME/Library/Logs/chicago-property-tracker"

if ! command -v cloudflared >/dev/null 2>&1; then
    echo "ERROR: cloudflared not installed. Run: brew install cloudflared"
    exit 1
fi
CLOUDFLARED="$(command -v cloudflared)"

if [ ! -x "$REPO_DIR/backend/venv/bin/uvicorn" ]; then
    echo "ERROR: backend venv not set up at $REPO_DIR/backend/venv"
    echo "Run: cd backend && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
    exit 1
fi

mkdir -p "$AGENTS_DIR" "$LOGS_DIR"

render() {
    local src="$1" dst="$2"
    sed -e "s|{{REPO_DIR}}|$REPO_DIR|g" \
        -e "s|{{HOME}}|$HOME_DIR|g" \
        -e "s|{{CLOUDFLARED}}|$CLOUDFLARED|g" \
        "$src" > "$dst"
    echo "  ✓ wrote $dst"
}

reload() {
    local label="$1" plist="$2"
    local domain="gui/$(id -u)"
    if launchctl print "$domain/$label" >/dev/null 2>&1; then
        # Already loaded — kickstart restarts it in place atomically.
        launchctl kickstart -k "$domain/$label" >/dev/null 2>&1
        echo "  ✓ restarted $label"
    else
        launchctl bootstrap "$domain" "$plist"
        echo "  ✓ loaded $label"
    fi
}

cd "$(dirname "${BASH_SOURCE[0]}")"

render "com.chicagopropertytracker.backend.plist.template" \
       "$AGENTS_DIR/com.chicagopropertytracker.backend.plist"

render "com.chicagopropertytracker.tunnel.plist.template" \
       "$AGENTS_DIR/com.chicagopropertytracker.tunnel.plist"

reload "com.chicagopropertytracker.backend" \
       "$AGENTS_DIR/com.chicagopropertytracker.backend.plist"

reload "com.chicagopropertytracker.tunnel" \
       "$AGENTS_DIR/com.chicagopropertytracker.tunnel.plist"

echo
echo "Both services installed and started. Tail logs with:"
echo "  tail -f $LOGS_DIR/backend.log"
echo "  tail -f $LOGS_DIR/tunnel.err.log"
echo
echo "Find current tunnel URL:"
echo "  grep -oE 'https://[a-z-]+\\.trycloudflare\\.com' $LOGS_DIR/tunnel.err.log | tail -1"
