"""Tests for Slack ingester."""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSlackIngester:
    """Tests for SlackIngester."""

    @patch('digiman.ingesters.slack.SLACK_BOT_TOKEN', None)
    @patch('digiman.ingesters.slack.SLACK_USER_ID', None)
    def test_init_with_explicit_values(self):
        """Test initialization with explicit values."""
        from digiman.ingesters.slack import SlackIngester
        ingester = SlackIngester(bot_token="test-token", user_id="U12345")
        assert ingester.bot_token == "test-token"
        assert ingester.user_id == "U12345"

    @patch('digiman.ingesters.slack.SLACK_BOT_TOKEN', None)
    @patch('digiman.ingesters.slack.SLACK_USER_ID', None)
    def test_get_recent_mentions_no_credentials(self):
        """Test handling of missing credentials."""
        from digiman.ingesters.slack import SlackIngester
        ingester = SlackIngester(bot_token=None, user_id=None)
        mentions = ingester.get_recent_mentions()
        assert mentions == []

    @patch('digiman.ingesters.slack.SLACK_BOT_TOKEN', None)
    @patch('digiman.ingesters.slack.SLACK_USER_ID', None)
    @patch('digiman.ingesters.slack.ProcessedSource')
    def test_get_recent_mentions_success(self, mock_processed):
        """Test successful mention fetching."""
        from digiman.ingesters.slack import SlackIngester

        mock_processed.is_processed.return_value = False

        ingester = SlackIngester(bot_token="xoxb-test", user_id="U12345")

        # Mock the client
        mock_client = MagicMock()
        mock_client.conversations_list.return_value = {
            "channels": [
                {"id": "C12345", "name": "general", "is_member": True}
            ],
            "response_metadata": {}
        }
        mock_client.conversations_history.return_value = {
            "messages": [
                {
                    "ts": "1706500000.000000",
                    "text": "Hey <@U12345> can you review this?",
                    "user": "U67890"
                }
            ]
        }
        mock_client.users_info.return_value = {
            "user": {"real_name": "John Doe", "name": "john"}
        }

        ingester._client = mock_client

        mentions = ingester.get_recent_mentions(hours=24)

        assert len(mentions) == 1
        assert "review" in mentions[0]["text"]
        assert mentions[0]["channel_name"] == "general"

    @patch('digiman.ingesters.slack.SLACK_BOT_TOKEN', None)
    @patch('digiman.ingesters.slack.SLACK_USER_ID', None)
    def test_get_content_for_extraction(self):
        """Test content formatting for extraction."""
        from digiman.ingesters.slack import SlackIngester
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
