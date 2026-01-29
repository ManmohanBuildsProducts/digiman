"""Tests for Slack ingester."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from digiman.ingesters.slack import SlackIngester


class TestSlackIngester:
    """Tests for SlackIngester."""

    def test_init_with_explicit_none(self):
        """Test initialization with explicit None values."""
        # When explicit None is passed, it should stay None (not fall back to config)
        ingester = SlackIngester(bot_token="", user_id="")
        assert ingester.bot_token == ""
        assert ingester.user_id == ""

    def test_get_recent_mentions_no_credentials(self):
        """Test handling of missing credentials."""
        ingester = SlackIngester(bot_token=None, user_id=None)
        mentions = ingester.get_recent_mentions()
        assert mentions == []

    @patch('digiman.ingesters.slack.SlackIngester.client')
    def test_get_recent_mentions_success(self, mock_client):
        """Test successful mention fetching."""
        mock_client.search_messages.return_value = {
            "messages": {
                "matches": [
                    {
                        "ts": "1706500000.000000",
                        "text": "Hey <@U12345> can you review this?",
                        "channel": {"id": "C12345", "name": "general"},
                        "user": "U67890",
                        "username": "john",
                        "permalink": "https://slack.com/archives/..."
                    }
                ]
            }
        }

        ingester = SlackIngester(bot_token="xoxb-test", user_id="U12345")
        ingester._client = mock_client

        mentions = ingester.get_recent_mentions(hours=24)

        assert len(mentions) == 1
        assert "review" in mentions[0]["text"]
        assert mentions[0]["channel_name"] == "general"

    def test_get_content_for_extraction(self):
        """Test content formatting for extraction."""
        ingester = SlackIngester(bot_token=None, user_id=None)

        mention = {
            "channel_name": "product-team",
            "username": "sarah",
            "text": "Can you review the design doc?",
            "thread_ts": None,
            "channel_id": None
        }

        content = ingester.get_content_for_extraction(mention)

        assert "Channel: #product-team" in content
        assert "@sarah" in content
        assert "review the design doc" in content
