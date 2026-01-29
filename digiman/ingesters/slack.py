"""Slack @mentions and unread threads ingester.

Uses bot token compatible APIs (conversations.list + conversations.history)
instead of search.messages which requires a user token.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from digiman.config import SLACK_BOT_TOKEN, SLACK_USER_ID
from digiman.models import ProcessedSource


class SlackIngester:
    """Fetch Slack @mentions using bot-compatible APIs."""

    def __init__(self, bot_token: Optional[str] = None, user_id: Optional[str] = None):
        self.bot_token = bot_token or SLACK_BOT_TOKEN
        self.user_id = user_id or SLACK_USER_ID
        self._client = None
        self._channel_cache = {}

    @property
    def client(self):
        """Lazy-load Slack client."""
        if self._client is None:
            if not self.bot_token:
                raise ValueError("SLACK_BOT_TOKEN not configured")
            from slack_sdk import WebClient
            self._client = WebClient(token=self.bot_token)
        return self._client

    def _get_channels(self) -> List[Dict[str, Any]]:
        """Get all channels the bot is a member of."""
        channels = []
        cursor = None

        try:
            while True:
                # Only request channel types we have scopes for
                # Add im:read scope to your Slack app to include DMs
                response = self.client.conversations_list(
                    types="public_channel,private_channel,mpim",
                    exclude_archived=True,
                    limit=200,
                    cursor=cursor
                )

                for channel in response.get("channels", []):
                    if channel.get("is_member", False):
                        channels.append(channel)
                        self._channel_cache[channel["id"]] = channel.get("name", "DM")

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

        except Exception as e:
            print(f"⚠️  Error listing channels: {e}")

        return channels

    def _get_channel_name(self, channel_id: str) -> str:
        """Get channel name from cache or API."""
        if channel_id in self._channel_cache:
            return self._channel_cache[channel_id]

        try:
            response = self.client.conversations_info(channel=channel_id)
            name = response.get("channel", {}).get("name", "Unknown")
            self._channel_cache[channel_id] = name
            return name
        except Exception:
            return "Unknown"

    def get_recent_mentions(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get @mentions from the last N hours using bot-compatible APIs."""
        if not self.bot_token or not self.user_id:
            print("⚠️  Slack credentials not configured")
            return []

        try:
            oldest = (datetime.now() - timedelta(hours=hours)).timestamp()
            mentions = []

            # Get all channels the bot is in
            channels = self._get_channels()
            print(f"📢 Scanning {len(channels)} channels for mentions...")

            mention_pattern = f"<@{self.user_id}>"

            for channel in channels:
                channel_id = channel["id"]
                channel_name = channel.get("name", "DM")

                try:
                    # Get recent messages from this channel
                    response = self.client.conversations_history(
                        channel=channel_id,
                        oldest=str(oldest),
                        limit=100
                    )

                    for msg in response.get("messages", []):
                        text = msg.get("text", "")

                        # Check if message mentions our user
                        if mention_pattern not in text:
                            continue

                        msg_id = f"{channel_id}_{msg.get('ts', '')}"

                        # Skip if already processed
                        if ProcessedSource.is_processed("slack", msg_id):
                            continue

                        ts = float(msg.get("ts", 0))

                        # Get username
                        user_id = msg.get("user", "")
                        username = self._get_username(user_id) if user_id else "unknown"

                        # Build permalink
                        permalink = f"https://slack.com/archives/{channel_id}/p{msg.get('ts', '').replace('.', '')}"

                        mention = {
                            "id": msg_id,
                            "channel_id": channel_id,
                            "channel_name": channel_name,
                            "text": text,
                            "user": user_id,
                            "username": username,
                            "timestamp": ts,
                            "permalink": permalink,
                            "thread_ts": msg.get("thread_ts"),
                        }

                        mentions.append(mention)

                except Exception:
                    # Skip channels we can't read (permissions, etc)
                    continue

            # Sort by timestamp descending
            mentions.sort(key=lambda x: x["timestamp"], reverse=True)
            print(f"📬 Found {len(mentions)} new mentions")

            return mentions

        except Exception as e:
            print(f"⚠️  Error fetching Slack mentions: {e}")
            return []

    def _get_username(self, user_id: str) -> str:
        """Get username from user ID."""
        try:
            response = self.client.users_info(user=user_id)
            user = response.get("user", {})
            return user.get("real_name") or user.get("name") or user_id
        except Exception:
            return user_id

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
