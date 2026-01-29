"""Pytest fixtures for Digiman tests."""

import os
import sys
import tempfile
import pytest
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    # Create temp file for test DB
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Patch the config module BEFORE importing models
    with patch('digiman.config.DATABASE_PATH', db_path):
        # Also patch it in the models module which may have already imported it
        import digiman.models.todo as todo_module
        original_path = todo_module.DATABASE_PATH if hasattr(todo_module, 'DATABASE_PATH') else None

        # Patch get_db_path to return our test path
        original_get_db_path = todo_module.get_db_path
        todo_module.get_db_path = lambda: __import__('pathlib').Path(db_path)

        # Import after patching
        from digiman.models import init_db

        # Initialize fresh database
        init_db()

        yield db_path

        # Restore original
        todo_module.get_db_path = original_get_db_path

    # Cleanup
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def client(test_db):
    """Create Flask test client with test database."""
    from digiman.app import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def sample_todo(test_db):
    """Create a sample todo for testing."""
    from digiman.models import Todo

    todo = Todo(
        title="Test todo item",
        description="Test description",
        timeline_type="date",
        due_date="2026-01-29",
        source_type="manual"
    )
    todo.save()
    return todo


@pytest.fixture
def sample_suggestion(test_db):
    """Create a sample suggestion for testing."""
    from digiman.models import Todo

    suggestion = Todo(
        title="Test suggestion from meeting",
        source_type="granola",
        source_id="test-meeting-123",
        source_context="Team Standup",
        is_suggestion=True
    )
    suggestion.save()
    return suggestion
