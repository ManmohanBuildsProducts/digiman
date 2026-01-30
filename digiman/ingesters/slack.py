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

    def get_surrounding_messages(self, channel_id: str, message_ts: str, before: int = 3, after: int = 3) -> List[Dict[str, Any]]:
        """Get messages surrounding a specific message in a channel.

        Args:
            channel_id: The channel ID
            message_ts: Timestamp of the target message
            before: Number of messages before the target
            after: Number of messages after the target

        Returns:
            List of messages in chronological order
        """
        try:
            # Get messages including and before the target
            response_before = self.client.conversations_history(
                channel=channel_id,
                latest=message_ts,
                limit=before + 1,  # +1 to include the target message
                inclusive=True
            )
            messages_before = response_before.get("messages", [])

            # Get messages after the target
            response_after = self.client.conversations_history(
                channel=channel_id,
                oldest=message_ts,
                limit=after + 1,  # +1 because oldest is inclusive
                inclusive=False
            )
            messages_after = response_after.get("messages", [])

            # Combine and sort by timestamp
            all_messages = messages_before + messages_after
            # Remove duplicates based on ts
            seen = set()
            unique_messages = []
            for msg in all_messages:
                ts = msg.get("ts")
                if ts and ts not in seen:
                    seen.add(ts)
                    unique_messages.append(msg)

            # Sort chronologically (oldest first)
            unique_messages.sort(key=lambda x: float(x.get("ts", 0)))

            return unique_messages

        except Exception as e:
            print(f"⚠️  Error fetching surrounding messages: {e}")
            return []

    def get_full_context(self, mention: Dict[str, Any]) -> str:
        """Get full context for a mention - thread or surrounding messages.

        Args:
            mention: The mention dict from get_recent_mentions()

        Returns:
            Formatted string with full context for AI extraction
        """
        parts = []
        parts.append(f"Channel: #{mention.get('channel_name', 'unknown')}")
        parts.append(f"From: @{mention.get('username', 'unknown')}")
        parts.append("")

        channel_id = mention.get("channel_id")
        thread_ts = mention.get("thread_ts")
        message_ts = mention.get("id", "").split("_")[-1] if mention.get("id") else None

        if thread_ts and channel_id:
            # It's a thread - get full thread context
            parts.append("## Thread Context")
            thread_messages = self.get_thread_context(channel_id, thread_ts, limit=15)

            for msg in thread_messages:
                user_id = msg.get("user", "")
                username = self._get_username(user_id) if user_id else "unknown"
                text = msg.get("text", "")
                # Clean up Slack formatting
                text = self._clean_slack_text(text)
                parts.append(f"@{username}: {text}")
            parts.append("")

        elif channel_id and message_ts:
            # It's a channel message - get surrounding context
            parts.append("## Channel Context (surrounding messages)")
            surrounding = self.get_surrounding_messages(channel_id, message_ts, before=3, after=3)

            for msg in surrounding:
                user_id = msg.get("user", "")
                username = self._get_username(user_id) if user_id else "unknown"
                text = msg.get("text", "")
                # Clean up Slack formatting
                text = self._clean_slack_text(text)
                # Mark the target message
                is_target = msg.get("ts") == message_ts
                prefix = ">>> " if is_target else ""
                parts.append(f"{prefix}@{username}: {text}")
            parts.append("")
        else:
            # Fallback - just the message
            parts.append("## Message")
            parts.append(mention.get("text", ""))
            parts.append("")

        return "\n".join(parts)

    def _clean_slack_text(self, text: str) -> str:
        """Clean Slack formatting from text."""
        import re
        # Remove user mentions like <@U123>
        cleaned = re.sub(r'<@[A-Z0-9]+>', '@user', text)
        # Convert channel links
        cleaned = re.sub(r'<#[A-Z0-9]+\|([^>]+)>', r'#\1', cleaned)
        # Convert URL links with text
        cleaned = re.sub(r'<(https?://[^|>]+)\|([^>]+)>', r'\2', cleaned)
        # Convert plain URLs
        cleaned = re.sub(r'<(https?://[^>]+)>', r'\1', cleaned)
        return cleaned

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
