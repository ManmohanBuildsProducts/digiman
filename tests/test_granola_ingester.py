"""Tests for Granola ingester."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

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
        # Real Granola cache format: double-JSON with state.documents as dict
        cache_data = {
            "cache": json.dumps({
                "state": {
                    "documents": {},
                    "documentPanels": {}
                }
            })
        }
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(json.dumps(cache_data))

        ingester = GranolaIngester(cache_path=str(cache_file))
        meetings = ingester.get_recent_meetings()
        assert meetings == []

    @patch('digiman.ingesters.granola.ProcessedSource')
    def test_get_recent_meetings_with_data(self, mock_processed, tmp_path):
        """Test extraction of meeting data."""
        mock_processed.is_processed.return_value = False

        now = datetime.utcnow()
        # Real Granola cache format: double-JSON, documents is dict keyed by ID
        inner_state = {
            "state": {
                "documents": {
                    "meeting-1": {
                        "title": "Team Standup",
                        "created_at": now.isoformat() + "Z",
                        "notes": {
                            "content": [
                                {"type": "paragraph", "content": [{"type": "text", "text": "Review PR"}]},
                                {"type": "paragraph", "content": [{"type": "text", "text": "Deploy to staging"}]}
                            ]
                        }
                    }
                },
                "documentPanels": {
                    "meeting-1": {
                        "panel-1": {
                            "title": "Summary",
                            "content": "<p>Daily standup meeting</p>"
                        }
                    }
                }
            }
        }
        cache_data = {"cache": json.dumps(inner_state)}

        cache_file = tmp_path / "cache.json"
        cache_file.write_text(json.dumps(cache_data))

        ingester = GranolaIngester(cache_path=str(cache_file))
        meetings = ingester.get_recent_meetings(hours=24)

        assert len(meetings) == 1
        assert meetings[0]["title"] == "Team Standup"
        assert "Review PR" in meetings[0]["notes_text"]

    @patch('digiman.ingesters.granola.ProcessedSource')
    def test_get_recent_meetings_filters_old(self, mock_processed, tmp_path):
        """Test that old meetings are filtered out."""
        mock_processed.is_processed.return_value = False

        old_time = datetime.utcnow() - timedelta(hours=48)
        inner_state = {
            "state": {
                "documents": {
                    "old-meeting": {
                        "title": "Old Meeting",
                        "created_at": old_time.isoformat() + "Z",
                        "notes": {"content": []}
                    }
                },
                "documentPanels": {}
            }
        }
        cache_data = {"cache": json.dumps(inner_state)}

        cache_file = tmp_path / "cache.json"
        cache_file.write_text(json.dumps(cache_data))

        ingester = GranolaIngester(cache_path=str(cache_file))
        meetings = ingester.get_recent_meetings(hours=24)

        assert len(meetings) == 0

    def test_get_content_for_extraction(self, tmp_path):
        """Test content formatting for extraction."""
        ingester = GranolaIngester(cache_path=str(tmp_path / "dummy.json"))

        # Use the correct field names that the real code expects
        meeting = {
            "title": "Planning Meeting",
            "notes_text": "- Task 1\n- Task 2",
            "summary_text": "Sprint planning",
            "action_items": ["Follow up with team", "Update docs"]
        }

        content = ingester.get_content_for_extraction(meeting)

        assert "Meeting: Planning Meeting" in content
        assert "Task 1" in content
        assert "Sprint planning" in content
