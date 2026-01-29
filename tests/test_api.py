"""Tests for API endpoints."""

import json
import pytest
from datetime import date


class TestTodoAPI:
    """Tests for Todo API endpoints."""

    def test_get_todos(self, client, sample_todo):
        """Test GET /api/todos returns todos."""
        response = client.get('/api/todos')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_create_todo(self, client, test_db):
        """Test POST /api/todos creates a todo."""
        response = client.post('/api/todos',
            data=json.dumps({
                'title': 'New test todo',
                'timeline_type': 'date',
                'due_date': date.today().isoformat()
            }),
            content_type='application/json'
        )

        assert response.status_code in [200, 201]  # 201 for created
        data = json.loads(response.data)
        assert data['title'] == 'New test todo'
        assert data['is_suggestion'] == False

    def test_create_todo_missing_title(self, client, test_db):
        """Test POST /api/todos with missing title returns error."""
        response = client.post('/api/todos',
            data=json.dumps({
                'timeline_type': 'date'
            }),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_toggle_todo(self, client, sample_todo):
        """Test POST /api/todos/<id>/toggle completes todo."""
        response = client.post(f'/api/todos/{sample_todo.id}/toggle')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'completed'

    def test_toggle_todo_twice(self, client, sample_todo):
        """Test toggling twice uncompletes todo."""
        # First toggle - complete
        client.post(f'/api/todos/{sample_todo.id}/toggle')
        # Second toggle - uncomplete
        response = client.post(f'/api/todos/{sample_todo.id}/toggle')

        data = json.loads(response.data)
        assert data['status'] == 'pending'

    def test_update_todo(self, client, sample_todo):
        """Test PUT /api/todos/<id> updates todo."""
        response = client.put(f'/api/todos/{sample_todo.id}',
            data=json.dumps({
                'title': 'Updated title',
                'description': 'Updated description'
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Updated title'

    def test_delete_todo(self, client, sample_todo):
        """Test DELETE /api/todos/<id> deletes todo."""
        response = client.delete(f'/api/todos/{sample_todo.id}')

        assert response.status_code == 200

        # Verify deletion
        get_response = client.get(f'/api/todos/{sample_todo.id}')
        assert get_response.status_code == 404

    def test_get_nonexistent_todo(self, client, test_db):
        """Test GET /api/todos/<id> for nonexistent todo."""
        response = client.get('/api/todos/99999')
        assert response.status_code == 404


class TestSuggestionAPI:
    """Tests for Suggestion API endpoints."""

    def test_accept_suggestion_to_today(self, client, sample_suggestion):
        """Test accepting suggestion and adding to today."""
        response = client.post(
            f'/api/suggestions/{sample_suggestion.id}/accept',
            data=json.dumps({'timeline_type': 'today'}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['is_suggestion'] == False
        assert data['timeline_type'] == 'date'
        assert data['due_date'] == date.today().isoformat()

    def test_accept_suggestion_to_week(self, client, sample_suggestion):
        """Test accepting suggestion and adding to this week."""
        response = client.post(
            f'/api/suggestions/{sample_suggestion.id}/accept',
            data=json.dumps({'timeline_type': 'this_week'}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['is_suggestion'] == False
        assert data['timeline_type'] == 'week'

    def test_discard_suggestion(self, client, sample_suggestion):
        """Test discarding a suggestion."""
        response = client.post(
            f'/api/suggestions/{sample_suggestion.id}/discard',
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True

    def test_accept_nonexistent_suggestion(self, client, test_db):
        """Test accepting nonexistent suggestion returns error."""
        response = client.post(
            '/api/suggestions/99999/accept',
            data=json.dumps({'timeline_type': 'today'}),
            content_type='application/json'
        )

        assert response.status_code == 404

    def test_accept_non_suggestion(self, client, sample_todo):
        """Test accepting a regular todo (not suggestion) returns error."""
        response = client.post(
            f'/api/suggestions/{sample_todo.id}/accept',
            data=json.dumps({'timeline_type': 'today'}),
            content_type='application/json'
        )

        assert response.status_code == 404  # Not a suggestion


class TestHomepage:
    """Tests for homepage rendering."""

    def test_homepage_loads(self, client, test_db):
        """Test homepage returns 200."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Digiman' in response.data

    def test_homepage_shows_suggestions_section(self, client, sample_suggestion):
        """Test homepage shows suggestions when they exist."""
        response = client.get('/')

        assert response.status_code == 200
        assert b'suggestions-section' in response.data
        assert b'Test suggestion from meeting' in response.data

    def test_homepage_shows_today_section(self, client, sample_todo):
        """Test homepage shows today section."""
        response = client.get('/')

        assert response.status_code == 200
        assert b'today-section' in response.data
