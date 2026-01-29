"""Slack morning briefing push notification."""

from datetime import date, datetime
from typing import Optional

from digiman.config import SLACK_BOT_TOKEN, SLACK_USER_ID
from digiman.models import Todo


class SlackPusher:
    """Send morning briefing to Slack DM."""

    def __init__(self, bot_token: Optional[str] = None, user_id: Optional[str] = None):
        self.bot_token = bot_token or SLACK_BOT_TOKEN
        self.user_id = user_id or SLACK_USER_ID
        self._client = None

    @property
    def client(self):
        """Lazy-load Slack client."""
        if self._client is None:
            if not self.bot_token:
                raise ValueError("SLACK_BOT_TOKEN not configured")
            from slack_sdk import WebClient
            self._client = WebClient(token=self.bot_token)
        return self._client

    def format_briefing(self, todos: dict) -> str:
        """Format the morning briefing message."""
        today = date.today()
        lines = [
            f"🧠 *Digiman Daily Briefing - {today.strftime('%b %d, %Y')}*",
            ""
        ]

        # Overdue
        if todos.get("overdue"):
            lines.append(f"🔴 *ACTION NEEDED* ({len(todos['overdue'])} overdue):")
            for todo in todos["overdue"][:5]:  # Max 5
                context = f" - _{todo.source_context}_" if todo.source_context else ""
                days = f" ({todo.days_overdue} day{'s' if todo.days_overdue != 1 else ''})"
                lines.append(f"• {todo.title}{days}{context}")
            lines.append("")

        # Today
        if todos.get("today"):
            lines.append(f"📅 *TODAY* ({len(todos['today'])} items):")
            for todo in todos["today"][:5]:  # Max 5
                context = f" - _{todo.source_context}_" if todo.source_context else ""
                lines.append(f"• {todo.title}{context}")
            lines.append("")

        # This Week
        if todos.get("this_week"):
            lines.append(f"📆 *THIS WEEK* ({len(todos['this_week'])} items):")
            for todo in todos["this_week"][:3]:  # Max 3
                lines.append(f"• {todo.title}")
            lines.append("")

        # No items
        if not todos.get("overdue") and not todos.get("today") and not todos.get("this_week"):
            lines.append("✨ No pending tasks! Enjoy your day.")
            lines.append("")

        # Footer
        lines.append("🔗 Open Digiman: http://localhost:5000")

        return "\n".join(lines)

    def send_briefing(self) -> bool:
        """Send the morning briefing to user's DM.

        Returns True on success, False on failure.
        """
        if not self.bot_token or not self.user_id:
            print("⚠️  Slack credentials not configured")
            return False

        try:
            # Get today's todos
            todos = Todo.get_today()

            # Format message
            message = self.format_briefing(todos)

            # Open DM channel
            dm_response = self.client.conversations_open(users=[self.user_id])
            channel_id = dm_response["channel"]["id"]

            # Send message
            self.client.chat_postMessage(
                channel=channel_id,
                text=message,
                mrkdwn=True
            )

            print(f"✅ Morning briefing sent to Slack DM")
            return True

        except Exception as e:
            print(f"❌ Error sending Slack briefing: {e}")
            return False
