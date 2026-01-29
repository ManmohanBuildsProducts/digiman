#!/bin/bash
# Install Digiman Menu Bar App

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.digiman.menubar.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "📋 Installing Digiman Menu Bar App..."

# Create virtual environment if it doesn't exist
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
fi

# Activate and install dependencies
echo "Installing dependencies..."
source "$SCRIPT_DIR/venv/bin/activate"
pip install -q -r "$SCRIPT_DIR/requirements.txt"

# Make the script executable
chmod +x "$SCRIPT_DIR/digiman_menubar.py"

# Create LaunchAgents directory if needed
mkdir -p "$LAUNCH_AGENTS_DIR"

# Copy plist to LaunchAgents
echo "Setting up auto-start..."
cp "$SCRIPT_DIR/$PLIST_NAME" "$LAUNCH_AGENTS_DIR/"

# Unload if already loaded, then load
launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null || true
launchctl load "$LAUNCH_AGENTS_DIR/$PLIST_NAME"

echo ""
echo "✅ Digiman Menu Bar installed!"
echo ""
echo "The app should now appear in your menu bar (📋 icon)."
echo "It will auto-start on login."
echo ""
echo "To uninstall, run: ./uninstall.sh"
