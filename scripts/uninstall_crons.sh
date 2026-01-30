#!/bin/bash
# Uninstall Digiman cron jobs

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "Uninstalling Digiman cron jobs..."

# Unload all jobs
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.smartpaste.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.watchdog.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.nightly.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.morning.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.onwake.plist" 2>/dev/null || true

# Also handle legacy naming
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.nightly-sync.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.morning-push.plist" 2>/dev/null || true

# Remove plist files
rm -f "$LAUNCH_AGENTS_DIR/com.digiman.smartpaste.plist"
rm -f "$LAUNCH_AGENTS_DIR/com.digiman.watchdog.plist"
rm -f "$LAUNCH_AGENTS_DIR/com.digiman.nightly.plist"
rm -f "$LAUNCH_AGENTS_DIR/com.digiman.morning.plist"
rm -f "$LAUNCH_AGENTS_DIR/com.digiman.onwake.plist"
rm -f "$LAUNCH_AGENTS_DIR/com.digiman.nightly-sync.plist"
rm -f "$LAUNCH_AGENTS_DIR/com.digiman.morning-push.plist"

echo ""
echo "✅ Cron jobs uninstalled."
echo ""
echo "Note: Menu bar app and monitor plists not removed."
echo "To remove those:"
echo "  launchctl unload ~/Library/LaunchAgents/com.digiman.menubar.plist"
echo "  launchctl unload ~/Library/LaunchAgents/com.digiman.monitor.plist"
echo "  rm ~/Library/LaunchAgents/com.digiman.menubar.plist"
echo "  rm ~/Library/LaunchAgents/com.digiman.monitor.plist"
