#!/bin/bash
# Uninstall Digiman cron jobs

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "Uninstalling Digiman cron jobs..."

launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.nightly-sync.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.digiman.morning-push.plist" 2>/dev/null || true

rm -f "$LAUNCH_AGENTS_DIR/com.digiman.nightly-sync.plist"
rm -f "$LAUNCH_AGENTS_DIR/com.digiman.morning-push.plist"

echo "✅ Cron jobs uninstalled."
