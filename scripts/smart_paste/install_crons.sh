#!/bin/bash
# Install SMART_PASTE + Digiman cron jobs via launchd
#
# Schedule:
#   1:30 AM  - SMART_PASTE (Claude Code CLI processing)
#   2:00 AM  - Nightly Sync (extract action items to Digiman)
#   Every 15 min - Watchdog (catch-up if sync missed)
#   8:00 AM  - Morning Push (send to Slack)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "🧠 Installing SMART_PASTE + Digiman Cron Jobs"
echo "=============================================="
echo "Project directory: $PROJECT_DIR"
echo ""

# Create necessary directories
mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$HOME/.digiman/logs"

# Get API key from .env if it exists
ANTHROPIC_API_KEY=""
if [ -f "$PROJECT_DIR/.env" ]; then
    ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY "$PROJECT_DIR/.env" 2>/dev/null | cut -d'=' -f2 || echo "")
fi

# ========== SMART_PASTE Sync (1:30 AM) ==========
cat > "$LAUNCH_AGENTS_DIR/com.digiman.smartpaste.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.digiman.smartpaste</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>$SCRIPT_DIR/ensure_claude_code.sh &amp;&amp; $PROJECT_DIR/venv/bin/python $SCRIPT_DIR/smart_paste_sync.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>$HOME</string>
        <key>ANTHROPIC_API_KEY</key>
        <string>$ANTHROPIC_API_KEY</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>1</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$HOME/.digiman/logs/smartpaste.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.digiman/logs/smartpaste_error.log</string>
</dict>
</plist>
EOF

echo "✅ Created SMART_PASTE sync (runs at 1:30 AM)"

# ========== Watchdog (Every 15 minutes) ==========
cat > "$LAUNCH_AGENTS_DIR/com.digiman.watchdog.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.digiman.watchdog</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$SCRIPT_DIR/watchdog.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>$HOME</string>
    </dict>
    <key>StartInterval</key>
    <integer>900</integer>
    <key>StandardOutPath</key>
    <string>$HOME/.digiman/logs/watchdog.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.digiman/logs/watchdog_error.log</string>
</dict>
</plist>
EOF

echo "✅ Created Watchdog (runs every 15 minutes)"

# ========== Digiman Nightly Sync (2:00 AM) ==========
cat > "$LAUNCH_AGENTS_DIR/com.digiman.nightly.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.digiman.nightly</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/venv/bin/python</string>
        <string>$PROJECT_DIR/scripts/nightly_sync.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>$HOME</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$HOME/.digiman/logs/nightly.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.digiman/logs/nightly_error.log</string>
</dict>
</plist>
EOF

echo "✅ Created Digiman nightly sync (runs at 2:00 AM)"

# ========== Morning Push (8:00 AM) ==========
cat > "$LAUNCH_AGENTS_DIR/com.digiman.morning.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.digiman.morning</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/venv/bin/python</string>
        <string>$PROJECT_DIR/scripts/morning_push.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>$HOME</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$HOME/.digiman/logs/morning.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.digiman/logs/morning_error.log</string>
</dict>
</plist>
EOF

echo "✅ Created Morning push (runs at 8:00 AM)"

# ========== On-Wake Trigger (optional, for backfill) ==========
cat > "$LAUNCH_AGENTS_DIR/com.digiman.onwake.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.digiman.onwake</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$SCRIPT_DIR/watchdog.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>$HOME</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$HOME/.digiman/logs/onwake.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.digiman/logs/onwake_error.log</string>
</dict>
</plist>
EOF

echo "✅ Created On-Wake trigger (runs on login/wake)"

# Unload existing jobs (if any)
echo ""
echo "Unloading existing jobs..."
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.smartpaste.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.watchdog.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.nightly.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.morning.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.onwake.plist" 2>/dev/null || true

# Also unload old naming conventions
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.nightly-sync.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.morning-push.plist" 2>/dev/null || true

# Load new jobs
echo "Loading new jobs..."
launchctl load "$LAUNCH_AGENTS_DIR/com.digiman.smartpaste.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.digiman.watchdog.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.digiman.nightly.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.digiman.morning.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.digiman.onwake.plist"

echo ""
echo "=============================================="
echo "✅ All cron jobs installed!"
echo ""
echo "Schedule:"
echo "  🧠  1:30 AM - SMART_PASTE (Claude Code processing)"
echo "  🐕 Every 15 min - Watchdog (catch-up if missed)"
echo "  📝  2:00 AM - Nightly Sync (action items → Digiman)"
echo "  🌅  8:00 AM - Morning Push (todos → Slack)"
echo "  🔄 On Login  - On-Wake trigger (backfill check)"
echo ""
echo "Logs: ~/.digiman/logs/"
echo ""
echo "To check status:"
echo "  launchctl list | grep digiman"
echo ""
echo "To test manually:"
echo "  python $SCRIPT_DIR/smart_paste_sync.py"
echo "  bash $SCRIPT_DIR/watchdog.sh"
echo "  python $PROJECT_DIR/scripts/nightly_sync.py"
echo ""
echo "To uninstall:"
echo "  bash $PROJECT_DIR/scripts/uninstall_crons.sh"
