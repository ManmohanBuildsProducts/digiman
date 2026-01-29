"""Tests for Granola ingester."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from digiman.ingesters.granola import GranolaIngester


class TestGranolaIngester:
    """Tests for GranolaIngester."""

    def test_get_recent_meetings_no_file(self, tmp_path):
        """Test handling of missing cache file."""
        ingester = GranolaIngester(cache_path=str(tmp_path / "nonexistent.json"))
        meetings = ingester.get_recent_meetings()
        assert meetings == []

    def test_get_recent_meetings_empty_cache(self, tmp_path):
        """Test handling of empty cache."""
        cache_file = tmp_path / "cache.json"
        cache_file.write_text('{"documents": []}')

        ingester = GranolaIngester(cache_path=str(cache_file))
        meetings = ingester.get_recent_meetings()
        assert meetings == []

    def test_get_recent_meetings_with_data(self, tmp_path):
        """Test extraction of meeting data."""
        now = datetime.now()
        cache_data = {
            "documents": [
                {
                    "id": "meeting-1",
                    "title": "Team Standup",
                    "createdAt": now.isoformat(),
                    "notes_markdown": "# Action Items\n- Review PR\n- Deploy to staging",
                    "summary": "Daily standup meeting"
                }
            ]
        }

        cache_file = tmp_path / "cache.json"
        cache_file.write_text(json.dumps(cache_data))

        ingester = GranolaIngester(cache_path=str(cache_file))
        meetings = ingester.get_recent_meetings(hours=24)

        assert len(meetings) == 1
        assert meetings[0]["title"] == "Team Standup"
        assert "Review PR" in meetings[0]["notes_markdown"]

    def test_get_recent_meetings_filters_old(self, tmp_path):
        """Test that old meetings are filtered out."""
        old_time = datetime.now() - timedelta(hours=48)
        cache_data = {
            "documents": [
                {
                    "id": "old-meeting",
                    "title": "Old Meeting",
                    "createdAt": old_time.isoformat(),
                    "notes_markdown": "Old notes"
                }
            ]
        }

        cache_file = tmp_path / "cache.json"
        cache_file.write_text(json.dumps(cache_data))

        ingester = GranolaIngester(cache_path=str(cache_file))
        meetings = ingester.get_recent_meetings(hours=24)

        assert len(meetings) == 0

    def test_get_content_for_extraction(self, tmp_path):
        """Test content formatting for extraction."""
        ingester = GranolaIngester(cache_path=str(tmp_path / "dummy.json"))

        meeting = {
            "title": "Planning Meeting",
            "notes_markdown": "- Task 1\n- Task 2",
            "summary": "Sprint planning",
            "action_items": ["Follow up with team", "Update docs"]
        }

        content = ingester.get_content_for_extraction(meeting)

        assert "Meeting: Planning Meeting" in content
        assert "Task 1" in content
        assert "Sprint planning" in content
        assert "Follow up with team" in content
