#!/bin/bash
# Install launchd jobs for Digiman on macOS

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "🧠 Digiman Cron Installation"
echo "=================================="
echo "Project directory: $PROJECT_DIR"
echo ""

# Create LaunchAgents directory if needed
mkdir -p "$LAUNCH_AGENTS_DIR"

# Nightly sync plist (11 PM)
cat > "$LAUNCH_AGENTS_DIR/com.digiman.nightly-sync.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.digiman.nightly-sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$PROJECT_DIR/scripts/nightly_sync.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>23</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/data/nightly_sync.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/data/nightly_sync.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

echo "✓ Created nightly sync job (11 PM)"

# Morning push plist (8 AM)
cat > "$LAUNCH_AGENTS_DIR/com.digiman.morning-push.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.digiman.morning-push</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$PROJECT_DIR/scripts/morning_push.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/data/morning_push.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/data/morning_push.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

echo "✓ Created morning push job (8 AM)"

# Load the jobs
echo ""
echo "Loading jobs..."
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.nightly-sync.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.morning-push.plist" 2>/dev/null || true
launchctl load "$LAUNCH_AGENTS_DIR/com.digiman.nightly-sync.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.digiman.morning-push.plist"

echo "✓ Jobs loaded"
echo ""
echo "=================================="
echo "✅ Installation complete!"
echo ""
echo "Jobs scheduled:"
echo "  - Nightly sync: 11:00 PM daily"
echo "  - Morning push: 8:00 AM daily"
echo ""
echo "To manually run:"
echo "  python3 $PROJECT_DIR/scripts/nightly_sync.py"
echo "  python3 $PROJECT_DIR/scripts/morning_push.py"
echo ""
echo "To uninstall:"
echo "  launchctl unload $LAUNCH_AGENTS_DIR/com.digiman.nightly-sync.plist"
echo "  launchctl unload $LAUNCH_AGENTS_DIR/com.digiman.morning-push.plist"
echo "  rm $LAUNCH_AGENTS_DIR/com.digiman.*.plist"
