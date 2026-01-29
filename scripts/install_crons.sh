#!/bin/bash
# Install Digiman cron jobs (launchd)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHD_DIR="$SCRIPT_DIR/launchd"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "⏰ Installing Digiman Cron Jobs..."

# Create LaunchAgents directory if needed
mkdir -p "$LAUNCH_AGENTS_DIR"

# Install nightly sync (11 PM)
echo "Installing nightly sync (runs at 11:00 PM)..."
cp "$LAUNCHD_DIR/com.digiman.nightly-sync.plist" "$LAUNCH_AGENTS_DIR/"
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.nightly-sync.plist" 2>/dev/null || true
launchctl load "$LAUNCH_AGENTS_DIR/com.digiman.nightly-sync.plist"

# Install morning push (8 AM)
echo "Installing morning push (runs at 8:00 AM)..."
cp "$LAUNCHD_DIR/com.digiman.morning-push.plist" "$LAUNCH_AGENTS_DIR/"
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.morning-push.plist" 2>/dev/null || true
launchctl load "$LAUNCH_AGENTS_DIR/com.digiman.morning-push.plist"

echo ""
echo "✅ Cron jobs installed!"
echo ""
echo "Schedule:"
echo "  📝 Nightly Sync:  11:00 PM - Extract action items from Granola & Slack"
echo "  🌅 Morning Push:   8:00 AM - Send today's todos to Slack"
echo ""
echo "Logs:"
echo "  /tmp/digiman-nightly-sync.log"
echo "  /tmp/digiman-morning-push.log"
echo ""
echo "To run manually:"
echo "  python scripts/nightly_sync.py"
echo "  python scripts/morning_push.py"
echo ""
echo "To uninstall:"
echo "  ./scripts/uninstall_crons.sh"
