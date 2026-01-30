#!/bin/bash
# ensure_claude_code.sh - Pre-flight check for Claude Code CLI
#
# Ensures Claude Code is available before running SMART_PASTE sync.
# If not available, attempts to open Terminal with Claude.

set -e

LOG_FILE="$HOME/.digiman/logs/ensure_claude.log"
MAX_WAIT=60  # Maximum seconds to wait for Claude Code

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check if Claude Code CLI is installed
check_claude_installed() {
    if command -v claude &> /dev/null; then
        return 0
    fi
    return 1
}

# Check if Claude Code is responding
check_claude_responsive() {
    # Try to run a simple command
    timeout 10 claude --version &> /dev/null
    return $?
}

# Update dashboard status
update_dashboard() {
    local status="$1"
    local message="$2"
    python3 -c "
import json
from pathlib import Path
from datetime import datetime

f = Path.home() / '.digiman/cron_status.json'
d = {}
if f.exists():
    try:
        d = json.loads(f.read_text())
    except:
        pass

d.setdefault('claude_code', {})
d['claude_code']['available'] = '$status' == 'available'
d['claude_code']['last_check'] = datetime.now().isoformat()
d['claude_code']['message'] = '$message'

f.write_text(json.dumps(d, indent=2))
"
}

# Main check
main() {
    log "Checking Claude Code availability..."

    # First, check if Claude is installed
    if ! check_claude_installed; then
        log "ERROR: Claude Code CLI not installed"
        update_dashboard "unavailable" "CLI not installed"
        exit 1
    fi

    log "Claude Code CLI found"

    # Check if it's responsive
    if check_claude_responsive; then
        log "Claude Code is responsive"
        update_dashboard "available" "Ready"
        exit 0
    fi

    log "Claude Code not responding, attempting to start..."

    # Try to open Terminal with Claude Code
    # This uses AppleScript to open a new Terminal window
    osascript -e '
    tell application "Terminal"
        activate
        do script "claude --version && echo Claude Code ready"
    end tell
    ' 2>/dev/null || true

    # Wait for Claude Code to become responsive
    waited=0
    while [ $waited -lt $MAX_WAIT ]; do
        sleep 5
        waited=$((waited + 5))

        if check_claude_responsive; then
            log "Claude Code is now responsive (waited ${waited}s)"
            update_dashboard "available" "Started after ${waited}s"
            exit 0
        fi

        log "Waiting for Claude Code... (${waited}s/${MAX_WAIT}s)"
    done

    log "ERROR: Claude Code did not become responsive after ${MAX_WAIT}s"
    update_dashboard "unavailable" "Timeout waiting for response"
    exit 1
}

main "$@"
