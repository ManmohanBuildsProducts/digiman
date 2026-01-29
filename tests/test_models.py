"""Tests for database models."""

import pytest
from datetime import date, timedelta

from digiman.models import Todo, SyncHistory, ProcessedSource


class TestTodoModel:
    """Tests for Todo model."""

    def test_create_todo(self, test_db):
        """Test creating a basic todo."""
        todo = Todo(
            title="Buy groceries",
            timeline_type="date",
            due_date=date.today().isoformat()
        )
        todo.save()

        assert todo.id is not None
        assert todo.title == "Buy groceries"
        assert todo.status == "pending"
        assert todo.is_suggestion == False

    def test_create_suggestion(self, test_db):
        """Test creating a suggestion (not a todo yet)."""
        suggestion = Todo(
            title="Follow up on project",
            source_type="granola",
            source_context="Weekly sync",
            is_suggestion=True
        )
        suggestion.save()

        assert suggestion.id is not None
        assert suggestion.is_suggestion == True

    def test_complete_todo(self, sample_todo):
        """Test marking todo as complete."""
        sample_todo.complete()

        assert sample_todo.status == "completed"
        assert sample_todo.completed_at is not None

    def test_uncomplete_todo(self, sample_todo):
        """Test uncompleting a todo."""
        sample_todo.complete()
        sample_todo.uncomplete()

        assert sample_todo.status == "pending"
        assert sample_todo.completed_at is None

    def test_accept_suggestion_to_today(self, sample_suggestion):
        """Test accepting a suggestion and adding to today."""
        today = date.today().isoformat()
        sample_suggestion.accept_suggestion("date", today)

        assert sample_suggestion.is_suggestion == False
        assert sample_suggestion.timeline_type == "date"
        assert sample_suggestion.due_date == today

    def test_accept_suggestion_to_week(self, sample_suggestion):
        """Test accepting a suggestion and adding to this week."""
        current_week = date.today().isocalendar()
        week_str = f"{current_week[0]}-W{current_week[1]:02d}"
        sample_suggestion.accept_suggestion("week", week_str)

        assert sample_suggestion.is_suggestion == False
        assert sample_suggestion.timeline_type == "week"
        assert sample_suggestion.due_week == week_str

    def test_discard_suggestion(self, sample_suggestion):
        """Test discarding a suggestion."""
        sample_suggestion.discard_suggestion()

        assert sample_suggestion.status == "discarded"
        assert sample_suggestion.is_suggestion == False

    def test_get_today_excludes_suggestions(self, test_db):
        """Test that get_today() excludes suggestions."""
        today = date.today().isoformat()

        # Create a regular todo for today
        todo = Todo(
            title="Regular todo",
            source_type="manual",
            timeline_type="date",
            due_date=today,
            is_suggestion=False
        )
        todo.save()

        # Create a suggestion with same date
        suggestion = Todo(
            title="Suggestion item",
            source_type="granola",
            timeline_type="date",
            due_date=today,
            is_suggestion=True
        )
        suggestion.save()

        # Get today's todos
        result = Todo.get_today()

        # Should only include regular todo, not suggestion
        today_titles = [t.title for t in result["today"]]
        assert "Regular todo" in today_titles
        assert "Suggestion item" not in today_titles

    def test_get_suggestions(self, test_db):
        """Test getting all pending suggestions."""
        # Create suggestions
        for i in range(3):
            s = Todo(
                title=f"Suggestion {i}",
                source_type="slack",
                is_suggestion=True
            )
            s.save()

        # Create a regular todo (should not appear in suggestions)
        todo = Todo(
            title="Regular todo",
            source_type="manual",
            is_suggestion=False
        )
        todo.save()

        suggestions = Todo.get_suggestions()
        suggestion_titles = [s.title for s in suggestions]

        assert len(suggestions) == 3
        assert all(s.is_suggestion for s in suggestions)
        assert "Regular todo" not in suggestion_titles

    def test_overdue_detection(self, test_db):
        """Test overdue todo detection."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        todo = Todo(
            title="Overdue task",
            source_type="manual",
            timeline_type="date",
            due_date=yesterday,
            is_suggestion=False
        )
        todo.save()

        result = Todo.get_today()

        assert len(result["overdue"]) == 1
        assert result["overdue"][0].title == "Overdue task"

    def test_source_tracking(self, test_db):
        """Test that source_id and source_type are stored correctly."""
        todo = Todo(
            title="From Slack",
            source_type="slack",
            source_id="C123_1234567890.123456",
            source_context="#general"
        )
        todo.save()

        # Fetch it back
        fetched = Todo.get_by_id(todo.id)

        assert fetched.source_type == "slack"
        assert fetched.source_id == "C123_1234567890.123456"
        assert fetched.source_context == "#general"


class TestSyncHistory:
    """Tests for SyncHistory model."""

    def test_start_sync(self, test_db):
        """Test starting a sync record."""
        sync_id = SyncHistory.start("full")
        assert sync_id is not None
        assert isinstance(sync_id, int)

    def test_complete_sync(self, test_db):
        """Test completing a sync record."""
        sync_id = SyncHistory.start("full")
        # Should not raise
        SyncHistory.complete(sync_id, items_processed=10, items_extracted=5)

    def test_complete_sync_with_errors(self, test_db):
        """Test completing sync with errors."""
        sync_id = SyncHistory.start("nightly")
        # Should not raise
        SyncHistory.complete(sync_id, items_processed=5, items_extracted=2, errors="API timeout")


class TestProcessedSource:
    """Tests for ProcessedSource tracking."""

    def test_mark_and_check_processed(self, test_db):
        """Test marking and checking processed sources."""
        from digiman.models import ProcessedSource

        # Initially not processed
        assert ProcessedSource.is_processed("slack", "msg_123") == False

        # Mark as processed
        ProcessedSource.mark_processed("slack", "msg_123")

        # Now it should be processed
        assert ProcessedSource.is_processed("slack", "msg_123") == True

        # Different source should not be processed
        assert ProcessedSource.is_processed("slack", "msg_456") == False
        assert ProcessedSource.is_processed("granola", "msg_123") == False
