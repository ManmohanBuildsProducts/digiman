#!/bin/bash
# Double-click this to start Digiman menu bar app
cd "$(dirname "$0")"
./venv/bin/python digiman_menubar.py &
disown
osascript -e 'tell application "Terminal" to close front window' &
