#!/usr/bin/env bash
# Install Shellshuck binaries, desktop entry, and icon for the current user.
# Run from the project root after building with: pyinstaller shellshuck.spec

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"

echo "Installing Shellshuck..."

mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR"

# Binaries
cp "$PROJECT_ROOT/dist/shellshuck" "$BIN_DIR/shellshuck"
cp "$PROJECT_ROOT/dist/shellshuck-askpass" "$BIN_DIR/shellshuck-askpass"
chmod +x "$BIN_DIR/shellshuck" "$BIN_DIR/shellshuck-askpass"

# Desktop entry
cp "$SCRIPT_DIR/shellshuck.desktop" "$APP_DIR/shellshuck.desktop"

# Icon
cp "$PROJECT_ROOT/resources/icons/shellshuck.svg" "$ICON_DIR/shellshuck.svg"

# Refresh desktop database if available
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$APP_DIR" 2>/dev/null || true
fi

echo "Done. Make sure $BIN_DIR is on your PATH."
