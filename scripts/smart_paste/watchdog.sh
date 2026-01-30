#!/bin/bash
# watchdog.sh - Watchdog for SMART_PASTE sync
#
# Runs every 15 minutes to check if sync completed today.
# If 1:30 AM sync was missed (laptop offline, etc.), triggers catch-up.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
STATE_FILE="$HOME/.digiman/sync_state.json"
STATUS_FILE="$HOME/.digiman/cron_status.json"
LOG_FILE="$HOME/.digiman/logs/watchdog.log"
LOCK_FILE="$HOME/.digiman/smart_paste.lock"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Update dashboard status for watchdog
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

d.setdefault('jobs', {})
d['jobs']['watchdog'] = {
    'name': 'Watchdog',
    'icon': '🐕',
    'description': 'Ensures sync completes',
    'schedule': 'Every 15 min',
    'last_run': datetime.now().isoformat(),
    'last_status': '$status',
    'last_message': '$message'
}

f.write_text(json.dumps(d, indent=2))
"
}

# Check if sync already ran today
check_sync_today() {
    if [ ! -f "$STATE_FILE" ]; then
        return 1  # No state file = never synced
    fi

    # Get last successful sync timestamp
    local last_sync
    last_sync=$(python3 -c "
import json
from pathlib import Path
from datetime import datetime, date

f = Path.home() / '.digiman/sync_state.json'
if f.exists():
    try:
        d = json.loads(f.read_text())
        last = d.get('last_successful_sync')
        if last:
            dt = datetime.fromisoformat(last)
            # Check if it was today
            if dt.date() == date.today():
                print('yes')
            else:
                print('no')
        else:
            print('no')
    except:
        print('no')
else:
    print('no')
")

    [ "$last_sync" = "yes" ]
}

# Check if another sync is already running
check_lock() {
    if [ -f "$LOCK_FILE" ]; then
        # Check if the lock is stale (older than 30 minutes)
        local lock_age
        lock_age=$(python3 -c "
import os
from datetime import datetime
f = '$LOCK_FILE'
if os.path.exists(f):
    mtime = os.path.getmtime(f)
    age = datetime.now().timestamp() - mtime
    print(int(age))
else:
    print(0)
")
        if [ "$lock_age" -gt 1800 ]; then
            log "Removing stale lock file (${lock_age}s old)"
            rm -f "$LOCK_FILE"
            return 1
        fi
        return 0  # Lock exists and is fresh
    fi
    return 1  # No lock
}

# Check current hour to decide behavior
get_current_hour() {
    date +%H
}

# Main watchdog logic
main() {
    log "🐕 Watchdog check starting..."

    # If sync already ran today, skip
    if check_sync_today; then
        log "Sync already completed today - skipping"
        update_dashboard "skipped" "Sync already completed today"
        exit 0
    fi

    # If another sync is running, skip
    if check_lock; then
        log "Another sync is running - skipping"
        update_dashboard "skipped" "Sync already in progress"
        exit 0
    fi

    # Get current hour
    current_hour=$(get_current_hour)

    # Only trigger catch-up between 2 AM and 10 AM
    # (After 1:30 AM sync should have run, before 10 AM is reasonable catch-up time)
    if [ "$current_hour" -lt 2 ] || [ "$current_hour" -ge 10 ]; then
        log "Outside catch-up window (2-10 AM) - skipping"
        update_dashboard "skipped" "Outside catch-up window"
        exit 0
    fi

    # Sync hasn't run today and we're in the catch-up window - trigger it!
    log "🚨 Sync missed! Triggering catch-up..."
    update_dashboard "triggered" "Triggering catch-up sync"

    # Create lock file
    touch "$LOCK_FILE"

    # First, ensure Claude Code is available
    if ! bash "$SCRIPT_DIR/ensure_claude_code.sh"; then
        log "Claude Code not available - aborting"
        rm -f "$LOCK_FILE"
        update_dashboard "error" "Claude Code not available"
        exit 1
    fi

    # Run the sync
    log "Running SMART_PASTE sync..."
    if python3 "$SCRIPT_DIR/smart_paste_sync.py"; then
        log "✓ Catch-up sync completed successfully"
        update_dashboard "success" "Catch-up sync completed"
    else
        log "✗ Catch-up sync failed"
        update_dashboard "error" "Catch-up sync failed"
    fi

    # Remove lock
    rm -f "$LOCK_FILE"
}

main "$@"
