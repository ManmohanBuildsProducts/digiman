#!/bin/bash
# Install Digiman Monitor

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.digiman.monitor.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "⚡ Installing Digiman Monitor..."

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
chmod +x "$SCRIPT_DIR/monitor_app.py"

# Create LaunchAgent plist
cat > "$SCRIPT_DIR/$PLIST_NAME" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.digiman.monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>$SCRIPT_DIR/venv/bin/python</string>
        <string>$SCRIPT_DIR/monitor_app.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/tmp/digiman-monitor.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/digiman-monitor.err</string>
</dict>
</plist>
EOF

# Create LaunchAgents directory if needed
mkdir -p "$LAUNCH_AGENTS_DIR"

# Copy plist to LaunchAgents
cp "$SCRIPT_DIR/$PLIST_NAME" "$LAUNCH_AGENTS_DIR/"

# Unload if already loaded, then load
launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null || true
launchctl load "$LAUNCH_AGENTS_DIR/$PLIST_NAME"

# Create status directory
mkdir -p "$HOME/.digiman"

echo ""
echo "✅ Digiman Monitor installed!"
echo ""
echo "Look for ⚡ icon in your menu bar."
echo "Click it to:"
echo "  - See sync status"
echo "  - Open dashboard"
echo "  - Run sync manually"
echo ""
echo "Dashboard: http://localhost:5051"
