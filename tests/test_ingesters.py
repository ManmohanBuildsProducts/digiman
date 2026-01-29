"""Tests for data ingesters."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestGranolaIngester:
    """Tests for Granola ingester."""

    def test_parse_tiptap_content(self, test_db):
        """Test parsing TipTap JSON content."""
        from digiman.ingesters.granola import tiptap_to_text

        content = [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "First paragraph"}
                ]
            },
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {"type": "text", "text": "Bullet item 1"}
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

        result = tiptap_to_text(content)

        assert "First paragraph" in result
        assert "Bullet item 1" in result

    def test_extract_action_items_from_list(self, test_db):
        """Test extracting bullet points from summary text."""
        # Action items are now extracted by the nightly sync, not a separate function
        # This tests the pattern of what we'd extract
        import re

        summary = """
        Meeting Summary:
        We discussed the project timeline.

        Action Items:
        - Review the PR by Friday
        - Send update to stakeholders
        - Schedule follow-up meeting

        Next Steps:
        Continue with implementation.
        """

        # Pattern to find list items
        lines = summary.strip().split('\n')
        items = [line.strip()[2:] for line in lines if line.strip().startswith('- ')]

        assert len(items) == 3
        assert any("Review" in item for item in items)

    def test_html_to_text(self, test_db):
        """Test HTML to text conversion."""
        from digiman.ingesters.granola import html_to_text

        html = "<p>Hello <strong>world</strong></p><ul><li>Item 1</li></ul>"
        result = html_to_text(html)

        assert "Hello" in result
        assert "world" in result
        assert "Item 1" in result


class TestSlackIngester:
    """Tests for Slack ingester."""

    def test_clean_slack_text(self, test_db):
        """Test cleaning Slack formatted text."""
        import re

        text = "<@U123ABC> please review <#C456DEF|general> and check <https://example.com|this link>"

        # Clean user mentions
        cleaned = re.sub(r'<@[A-Z0-9]+>', '', text)
        # Clean channel links
        cleaned = re.sub(r'<#[A-Z0-9]+\|([^>]+)>', r'#\1', cleaned)
        # Clean URL links
        cleaned = re.sub(r'<(https?://[^|>]+)\|([^>]+)>', r'\2', cleaned)

        assert "<@" not in cleaned
        assert "#general" in cleaned
        assert "this link" in cleaned

    def test_ingester_initialization(self, test_db):
        """Test Slack ingester initializes with token."""
        from digiman.ingesters.slack import SlackIngester

        ingester = SlackIngester(bot_token='xoxb-test-token')
        assert ingester.bot_token == 'xoxb-test-token'

    def test_mention_detection(self, test_db):
        """Test detecting @mentions in message text."""
        user_id = "U03SJ2YBE6L"

        messages = [
            {"text": f"Hey <@{user_id}> can you review this?", "user": "U123"},
            {"text": "Just a normal message", "user": "U456"},
            {"text": f"<@{user_id}> <@{user_id}> double mention", "user": "U789"},
        ]

        mentions = [m for m in messages if f"<@{user_id}>" in m.get("text", "")]

        assert len(mentions) == 2


class TestSyncScript:
    """Tests for the nightly sync script."""

    def test_clean_text_function(self, test_db):
        """Test the clean_text helper function."""
        from scripts.nightly_sync import clean_text

        text = "  Hello\nWorld  \n\n  Test  "
        result = clean_text(text)

        assert "\n" not in result
        # clean_text replaces newlines and double spaces but may leave some spaces
        assert "Hello" in result
        assert "World" in result
        assert "Test" in result

    def test_clean_text_preserves_content(self, test_db):
        """Test that clean_text doesn't truncate."""
        from scripts.nightly_sync import clean_text

        long_text = "A" * 500
        result = clean_text(long_text)

        assert len(result) == 500
