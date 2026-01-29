#!/usr/bin/env python3
"""Morning push script - Run at 8 AM via cron/launchd."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from digiman.models import init_db
from digiman.notifiers import SlackPusher


def run_morning_push() -> bool:
    """Send morning briefing to Slack.

    Returns True on success, False on failure.
    """
    print("🧠 Digiman Morning Push")
    print("=" * 40)

    # Ensure database exists
    init_db()

    # Send briefing
    pusher = SlackPusher()
    success = pusher.send_briefing()

    if success:
        print("\n✅ Morning briefing sent!")
    else:
        print("\n❌ Failed to send morning briefing")

    return success


if __name__ == "__main__":
    success = run_morning_push()
    sys.exit(0 if success else 1)
