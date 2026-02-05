"""Slack morning briefing push notification."""

from datetime import date
from typing import Optional

from digiman.config import SLACK_BOT_TOKEN, SLACK_USER_ID

# Post briefings to #mydailyplanner (private channel)
BRIEFING_CHANNEL = "C093CG2KA1G"
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

    def format_briefing(self, todos: dict, suggestions: list = None) -> str:
        """Format the morning briefing message."""
        today = date.today()
        lines = [
            f"🧠 *Digiman Daily Briefing - {today.strftime('%A, %b %d, %Y')}*",
            ""
        ]

        # New Suggestions (from overnight sync) - grouped by source
        if suggestions:
            # Separate by source
            granola_suggestions = [s for s in suggestions if s.source_type == 'granola']
            slack_suggestions = [s for s in suggestions if s.source_type == 'slack']

            lines.append(f"💡 *NEW SUGGESTIONS* ({len(suggestions)} items to review)")
            lines.append("")

            # Granola suggestions - grouped by meeting
            if granola_suggestions:
                lines.append("*From Meetings:*")
                # Group by meeting (source_context)
                meetings = {}
                for sugg in granola_suggestions:
                    meeting = sugg.source_context or "Unknown Meeting"
                    if meeting not in meetings:
                        meetings[meeting] = []
                    meetings[meeting].append(sugg)

                for meeting_title, items in meetings.items():
                    lines.append(f"📝 _{meeting_title}_")
                    for sugg in items:
                        lines.append(f"    • {sugg.title}")
                lines.append("")

            # Slack suggestions
            if slack_suggestions:
                lines.append("*From Slack Mentions:*")
                for sugg in slack_suggestions:
                    channel = sugg.source_context or "#unknown"
                    lines.append(f"💬 {channel}: {sugg.title}")
                lines.append("")

        # Overdue - show all
        if todos.get("overdue"):
            lines.append(f"🔴 *OVERDUE* ({len(todos['overdue'])} items)")
            for todo in todos["overdue"]:
                days = f"({todo.days_overdue}d)" if todo.days_overdue else ""
                context = f" _{todo.source_context}_" if todo.source_context else ""
                lines.append(f"• {todo.title} {days}{context}")
            lines.append("")

        # Today - show all
        if todos.get("today"):
            lines.append(f"📅 *TODAY* ({len(todos['today'])} items)")
            for todo in todos["today"]:
                context = f" - _{todo.source_context}_" if todo.source_context else ""
                lines.append(f"• {todo.title}{context}")
            lines.append("")

        # This Week - show all
        if todos.get("this_week"):
            lines.append(f"📆 *THIS WEEK* ({len(todos['this_week'])} items)")
            for todo in todos["this_week"]:
                context = f" - _{todo.source_context}_" if todo.source_context else ""
                lines.append(f"• {todo.title}{context}")
            lines.append("")

        # No items at all
        if not suggestions and not todos.get("overdue") and not todos.get("today") and not todos.get("this_week"):
            lines.append("✨ All clear! No pending tasks.")
            lines.append("")

        # Footer
        lines.append("─────────────────────────")
        lines.append("🔗 <https://manmohanbuildsproducts.pythonanywhere.com|Open Digiman>")

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

            # Get pending suggestions
            suggestions = Todo.get_suggestions()

            # Format message
            message = self.format_briefing(todos, suggestions)

            # Send to #mydailyplanner channel
            self.client.chat_postMessage(
                channel=BRIEFING_CHANNEL,
                text=message,
                mrkdwn=True
            )

            print("✅ Morning briefing sent to #mydailyplanner")
            return True

        except Exception as e:
            print(f"❌ Error sending Slack briefing: {e}")
            return False
