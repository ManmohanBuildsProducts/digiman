#!/usr/bin/env python3
"""Morning push script - Run at 8 AM via cron/launchd."""

import sys
import time
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

    # Send briefing with retry (DNS may not be ready after Mac sleep)
    pusher = SlackPusher()
    max_attempts = 3
    delay = 30

    for attempt in range(1, max_attempts + 1):
        success = pusher.send_briefing()
        if success:
            print(f"\n✅ Morning briefing sent! (attempt {attempt}/{max_attempts})")
            return True

        if attempt < max_attempts:
            print(f"\n⚠️  Attempt {attempt}/{max_attempts} failed, retrying in {delay}s...")
            time.sleep(delay)

    print("\n❌ Failed to send morning briefing after all attempts")
    return False


if __name__ == "__main__":
    success = run_morning_push()
    sys.exit(0 if success else 1)
