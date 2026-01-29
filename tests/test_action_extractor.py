"""Tests for action extractor."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from digiman.extractors.action_extractor import ActionExtractor


class TestActionExtractor:
    """Tests for ActionExtractor."""

    def test_extract_empty_content(self):
        """Test handling of empty content."""
        extractor = ActionExtractor(api_key=None)
        items = extractor.extract("")
        assert items == []

    def test_extract_no_api_key(self):
        """Test handling of missing API key."""
        extractor = ActionExtractor(api_key=None)
        items = extractor.extract("Some meeting notes")
        assert items == []

    @patch('digiman.extractors.action_extractor.ActionExtractor.client')
    def test_extract_success(self, mock_client):
        """Test successful extraction."""
        mock_response = Mock()
        mock_response.content = [
            Mock(text='{"action_items": [{"title": "Review PR #123", "confidence": 0.95}]}')
        ]
        mock_client.messages.create.return_value = mock_response

        extractor = ActionExtractor(api_key="sk-ant-test")
        extractor._client = mock_client

        items = extractor.extract("Please review PR #123 by EOD")

        assert len(items) == 1
        assert items[0]["title"] == "Review PR #123"
        assert items[0]["confidence"] == 0.95

    @patch('digiman.extractors.action_extractor.ActionExtractor.client')
    def test_extract_with_markdown_response(self, mock_client):
        """Test extraction with markdown-wrapped JSON response."""
        mock_response = Mock()
        mock_response.content = [
            Mock(text='```json\n{"action_items": [{"title": "Send report", "confidence": 0.9}]}\n```')
        ]
        mock_client.messages.create.return_value = mock_response

        extractor = ActionExtractor(api_key="sk-ant-test")
        extractor._client = mock_client

        items = extractor.extract("Need to send the report")

        assert len(items) == 1
        assert items[0]["title"] == "Send report"

    @patch('digiman.extractors.action_extractor.ActionExtractor.client')
    def test_extract_with_timeline(self, mock_client):
        """Test extraction with timeline assignment."""
        mock_response = Mock()
        mock_response.content = [
            Mock(text='{"action_items": [{"title": "Update docs", "confidence": 0.85}]}')
        ]
        mock_client.messages.create.return_value = mock_response

        extractor = ActionExtractor(api_key="sk-ant-test")
        extractor._client = mock_client

        items = extractor.extract_with_timeline(
            "Update the documentation",
            default_date="2026-01-30"
        )

        assert len(items) == 1
        assert items[0]["timeline_type"] == "date"
        assert items[0]["due_date"] == "2026-01-30"

    @patch('digiman.extractors.action_extractor.ActionExtractor.client')
    def test_extract_invalid_json(self, mock_client):
        """Test handling of invalid JSON response."""
        mock_response = Mock()
        mock_response.content = [
            Mock(text='Not valid JSON')
        ]
        mock_client.messages.create.return_value = mock_response

        extractor = ActionExtractor(api_key="sk-ant-test")
        extractor._client = mock_client

        items = extractor.extract("Some content")

        assert items == []

    @patch('digiman.extractors.action_extractor.ActionExtractor.client')
    def test_extract_api_error(self, mock_client):
        """Test handling of API errors."""
        mock_client.messages.create.side_effect = Exception("API Error")

        extractor = ActionExtractor(api_key="sk-ant-test")
        extractor._client = mock_client

        items = extractor.extract("Some content")

        assert items == []
