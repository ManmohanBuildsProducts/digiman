"""Slack @mentions and unread threads ingester."""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from digiman.config import SLACK_BOT_TOKEN, SLACK_USER_ID
from digiman.models import ProcessedSource


class SlackIngester:
    """Fetch Slack @mentions and unread threads."""

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

    def get_recent_mentions(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get @mentions from the last N hours."""
        if not self.bot_token or not self.user_id:
            print("⚠️  Slack credentials not configured")
            return []

        try:
            # Calculate oldest timestamp
            oldest = (datetime.now() - timedelta(hours=hours)).timestamp()

            # Search for mentions
            response = self.client.search_messages(
                query=f"<@{self.user_id}>",
                sort="timestamp",
                sort_dir="desc",
                count=100
            )

            mentions = []
            matches = response.get("messages", {}).get("matches", [])

            for match in matches:
                # Skip if already processed
                msg_id = f"{match.get('channel', {}).get('id', '')}_{match.get('ts', '')}"
                if ProcessedSource.is_processed("slack", msg_id):
                    continue

                # Check timestamp
                ts = float(match.get("ts", 0))
                if ts < oldest:
                    continue

                # Get channel info
                channel = match.get("channel", {})
                channel_name = channel.get("name", "Unknown")

                # Build permalink
                permalink = match.get("permalink", "")

                mention = {
                    "id": msg_id,
                    "channel_id": channel.get("id", ""),
                    "channel_name": channel_name,
                    "text": match.get("text", ""),
                    "user": match.get("user", ""),
                    "username": match.get("username", ""),
                    "timestamp": ts,
                    "permalink": permalink,
                    "thread_ts": match.get("thread_ts"),
                }

                mentions.append(mention)

            return mentions

        except Exception as e:
            print(f"⚠️  Error fetching Slack mentions: {e}")
            return []

    def get_thread_context(self, channel_id: str, thread_ts: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get messages from a thread for context."""
        try:
            response = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=limit
            )
            return response.get("messages", [])
        except Exception as e:
            print(f"⚠️  Error fetching thread context: {e}")
            return []

    def get_content_for_extraction(self, mention: Dict[str, Any]) -> str:
        """Get content from a mention for action extraction."""
        parts = []

        parts.append(f"Channel: #{mention.get('channel_name', 'unknown')}")
        parts.append(f"From: @{mention.get('username', 'unknown')}")
        parts.append("")

        # Add the mention text
        parts.append("## Message")
        parts.append(mention.get("text", ""))
        parts.append("")

        # If it's a thread, get thread context
        if mention.get("thread_ts") and mention.get("channel_id"):
            thread_messages = self.get_thread_context(
                mention["channel_id"],
                mention["thread_ts"]
            )
            if thread_messages:
                parts.append("## Thread Context")
                for msg in thread_messages[-5:]:  # Last 5 messages
                    username = msg.get("username", msg.get("user", "unknown"))
                    text = msg.get("text", "")
                    parts.append(f"@{username}: {text}")
                parts.append("")

        return "\n".join(parts)

    def mark_processed(self, mention_id: str):
        """Mark a mention as processed."""
        ProcessedSource.mark_processed("slack", mention_id)
