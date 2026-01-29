#!/bin/bash
# Uninstall Digiman Menu Bar App

PLIST_NAME="com.digiman.menubar.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "Uninstalling Digiman Menu Bar App..."

# Stop and unload the launch agent
launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null || true

# Remove the plist
rm -f "$LAUNCH_AGENTS_DIR/$PLIST_NAME"

echo "✅ Digiman Menu Bar uninstalled."
echo "The app will no longer auto-start on login."
