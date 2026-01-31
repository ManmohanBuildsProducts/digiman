"""Flask application for Digiman."""

from datetime import date, timedelta
from flask import Flask, render_template, request, jsonify, send_from_directory
import calendar
import json

import os
import subprocess
from digiman.config import FLASK_SECRET_KEY, FLASK_DEBUG
from digiman.models import Todo, init_db

# Tag color palette (8 colors)
TAG_COLORS = [
    '#ef4444', '#f97316', '#eab308', '#22c55e',
    '#14b8a6', '#3b82f6', '#8b5cf6', '#ec4899'
]


def tag_color(tag_name: str) -> str:
    """Generate a consistent color for a tag name based on hash."""
    if not tag_name:
        return TAG_COLORS[0]
    hash_val = 0
    for char in tag_name:
        hash_val = ord(char) + ((hash_val << 5) - hash_val)
    return TAG_COLORS[abs(hash_val) % len(TAG_COLORS)]

# Deploy webhook secret (set in environment)
DEPLOY_SECRET = os.getenv("DEPLOY_SECRET", "")

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

# Register tag_color as a Jinja global function
app.jinja_env.globals['tag_color'] = tag_color


def get_request_data():
    """Get data from request, handling both JSON and form data."""
    if request.is_json:
        return request.get_json(force=True, silent=True) or {}
    elif request.form:
        return request.form.to_dict()
    elif request.data:
        try:
            return json.loads(request.data)
        except (json.JSONDecodeError, ValueError):
            pass


import re

def should_reject_suggestion(title: str, description: str = None) -> tuple[bool, str]:
    """
    Filter out non-actionable suggestions before import.

    Returns:
        (should_reject: bool, reason: str)
    """
    if not title:
        return True, "empty_title"

    title_lower = title.lower().strip()
    desc_lower = (description or "").lower().strip()
    combined = f"{title_lower} {desc_lower}"

    # 1. Test/placeholder items
    test_patterns = [
        r'^test\s',
        r'^suggestion\s*\d*$',
        r'^suggestion item',
        r'^follow up on project$',  # Too vague
        r'^imported suggestion$',
    ]
    for pattern in test_patterns:
        if re.match(pattern, title_lower):
            return True, "test_placeholder"

    # 2. Sick leave / OOO / status updates (not actionable for recipient)
    status_patterns = [
        r'(fever|sick|ill|unwell|body ache|not feeling well)',
        r'(leave|on leave|taking leave|will be on leave)',
        r'(ooo|out of office|working from home|wfh today)',
        r'(will resume|will be back|back tomorrow)',
        r'(holiday|vacation|pto)',
    ]
    for pattern in status_patterns:
        if re.search(pattern, combined):
            return True, "status_update"

    # 3. Simple questions (not tasks)
    simple_question_patterns = [
        r'^@?\w+:?\s*(joining\??|available\??|free\??|there\??)$',
        r'^(joining|available|free|there)\??$',
        r'are you (available|free|joining|there)',
        r'can (you|we) (join|sync|meet|talk)',
    ]
    for pattern in simple_question_patterns:
        if re.search(pattern, title_lower):
            return True, "simple_question"

    # 4. Past meeting requests (with specific times/dates that have passed)
    # These often contain "today" or specific times
    meeting_request_patterns = [
        r'(between|from)\s+\d{1,2}[:\-]\d{2}\s*(am|pm|to)',
        r'(4-5|5-6|6-7|3-4)\s*pm\s*(today)?',
        r'sync (today|now|at \d)',
    ]
    for pattern in meeting_request_patterns:
        if re.search(pattern, title_lower):
            return True, "meeting_request"

    # 5. FYI/informational messages (no action required)
    fyi_patterns = [
        r'^(fyi|heads up|just so you know|letting you know)',
        r'(for your (info|information|reference|awareness))',
    ]
    for pattern in fyi_patterns:
        if re.search(pattern, title_lower):
            return True, "fyi_message"

    # 6. Too short to be actionable (likely noise)
    if len(title) < 10:
        return True, "too_short"

    return False, ""
    return {}


@app.before_request
def ensure_db():
    """Ensure database is initialized before any request."""
    init_db()


@app.context_processor
def inject_global_data():
    """Inject global data into all templates."""
    try:
        suggestions = Todo.get_suggestions()
        all_tags = Todo.get_all_tags()
        active_tag = request.args.get('tag')
        return {
            "suggestion_count": len(suggestions),
            "all_tags": all_tags,
            "active_tag": active_tag
        }
    except:
        return {"suggestion_count": 0, "all_tags": {}, "active_tag": None}


# ============== Static Files ==============

@app.route("/robots.txt")
def robots():
    """Serve robots.txt for crawlers."""
    return send_from_directory(app.static_folder, "robots.txt")


# ============== Page Routes ==============

@app.route("/")
def index():
    """Today view - main dashboard."""
    tag_filter = request.args.get('tag')
    todos = Todo.get_today(tag_filter=tag_filter)
    suggestions = Todo.get_suggestions()
    today = date.today()
    current_week = today.isocalendar()
    week_str = f"{current_week[0]}-W{current_week[1]:02d}"

    # Count for sidebar badge
    todos_today_count = len(todos.get('today', [])) + len(todos.get('overdue', []))

    return render_template(
        "index.html",
        todos=todos,
        suggestions=suggestions,
        today=today,
        week_str=week_str,
        active_page="today",
        todos_today_count=todos_today_count
    )


@app.route("/inbox")
def inbox():
    """Inbox view - triage suggestions from Granola/Slack."""
    suggestions = Todo.get_suggestions()
    today = date.today()
    current_week = today.isocalendar()
    week_str = f"{current_week[0]}-W{current_week[1]:02d}"

    # Group suggestions by source
    granola_suggestions = [s for s in suggestions if s.source_type == "granola"]
    slack_suggestions = [s for s in suggestions if s.source_type == "slack"]

    return render_template(
        "inbox.html",
        suggestions=suggestions,
        granola_suggestions=granola_suggestions,
        slack_suggestions=slack_suggestions,
        today=today,
        week_str=week_str,
        active_page="inbox"
    )


@app.route("/calendar")
def calendar_view():
    """Calendar view."""
    year = request.args.get("year", date.today().year, type=int)
    month = request.args.get("month", date.today().month, type=int)

    # Get calendar data
    cal_data = Todo.get_calendar_data(year, month)

    # Generate calendar grid
    cal = calendar.Calendar(firstweekday=0)  # Monday first
    month_days = cal.monthdayscalendar(year, month)

    # Count todos per day for the calendar grid
    day_counts = {}
    today = date.today()
    for date_str, todos in cal_data["by_date"].items():
        d = date.fromisoformat(date_str)
        pending = [t for t in todos if t.status == "pending"]
        overdue = d < today and len(pending) > 0
        day_counts[d.day] = {"count": len(pending), "overdue": overdue}

    # Previous/next month
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year

    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year

    # Selected date (for displaying todos)
    selected_date = request.args.get("date", today.isoformat())

    return render_template(
        "calendar.html",
        year=year,
        month=month,
        month_name=calendar.month_name[month],
        month_days=month_days,
        day_counts=day_counts,
        cal_data=cal_data,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
        today=today,
        selected_date=selected_date,
        active_page="calendar"
    )


# ============== API Routes ==============

@app.route("/api/todos", methods=["GET"])
def api_get_todos():
    """Get all todos."""
    status = request.args.get("status")
    todos = Todo.get_all(status=status)
    return jsonify([t.to_dict() for t in todos])


@app.route("/api/todos", methods=["POST"])
def api_create_todo():
    """Create a new todo."""
    data = get_request_data()

    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Title required"}), 400

    # Parse tags - accept both comma-separated string and array
    tags_input = data.get("tags", [])
    if isinstance(tags_input, str):
        tags = [t.strip().lower() for t in tags_input.split(",") if t.strip()]
    else:
        tags = [t.strip().lower() for t in tags_input if t.strip()]

    todo = Todo(
        title=title,
        description=data.get("description"),
        source_type="manual",
        timeline_type=data.get("timeline_type", "date"),
        due_date=data.get("due_date") or date.today().isoformat(),
        due_week=data.get("due_week"),
        due_month=data.get("due_month"),
        tags=tags,
    )
    todo.save()

    # If HTMX request, return the partial
    if request.headers.get("HX-Request"):
        return render_template("partials/todo_item.html", todo=todo)

    return jsonify(todo.to_dict()), 201


@app.route("/api/todos/<int:todo_id>", methods=["GET"])
def api_get_todo(todo_id: int):
    """Get a single todo."""
    todo = Todo.get_by_id(todo_id)
    if not todo:
        return jsonify({"error": "Not found"}), 404
    return jsonify(todo.to_dict())


@app.route("/api/todos/<int:todo_id>", methods=["PUT", "PATCH"])
def api_update_todo(todo_id: int):
    """Update a todo."""
    todo = Todo.get_by_id(todo_id)
    if not todo:
        return jsonify({"error": "Not found"}), 404

    data = get_request_data()
    needs_save = False

    if "title" in data:
        todo.title = data["title"]
        needs_save = True
    if "description" in data:
        todo.description = data["description"]
        needs_save = True
    if "tags" in data:
        tags_input = data["tags"]
        if isinstance(tags_input, str):
            todo.tags = [t.strip().lower() for t in tags_input.split(",") if t.strip()]
        else:
            todo.tags = [t.strip().lower() for t in tags_input if t.strip()]
        needs_save = True
    if "status" in data:
        if data["status"] == "completed":
            todo.complete()
            needs_save = False  # complete() already saves
        else:
            todo.status = data["status"]
            needs_save = True

    if needs_save:
        todo.save()

    if request.headers.get("HX-Request"):
        return render_template("partials/todo_item.html", todo=todo)

    return jsonify(todo.to_dict())


@app.route("/api/todos/<int:todo_id>", methods=["DELETE"])
def api_delete_todo(todo_id: int):
    """Delete a todo."""
    if Todo.delete(todo_id):
        if request.headers.get("HX-Request"):
            return "", 200
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404


@app.route("/api/todos/<int:todo_id>/toggle", methods=["POST"])
def api_toggle_todo(todo_id: int):
    """Toggle todo completion status."""
    todo = Todo.get_by_id(todo_id)
    if not todo:
        return jsonify({"error": "Not found"}), 404

    if todo.status == "completed":
        todo.uncomplete()
    else:
        todo.complete()

    if request.headers.get("HX-Request"):
        return render_template("partials/todo_item.html", todo=todo)

    return jsonify(todo.to_dict())


@app.route("/api/todos/<int:todo_id>/reassign", methods=["POST"])
def api_reassign_todo(todo_id: int):
    """Reassign todo to different timeline."""
    todo = Todo.get_by_id(todo_id)
    if not todo:
        return jsonify({"error": "Not found"}), 404

    data = get_request_data()
    timeline_type = data.get("timeline_type", "date")
    value = data.get("value")

    # Handle special shortcuts
    if timeline_type == "today":
        timeline_type = "date"
        value = date.today().isoformat()
    elif timeline_type == "tomorrow":
        timeline_type = "date"
        value = (date.today() + timedelta(days=1)).isoformat()
    elif timeline_type == "this_week":
        timeline_type = "week"
        current_week = date.today().isocalendar()
        value = f"{current_week[0]}-W{current_week[1]:02d}"
    elif timeline_type == "this_month":
        timeline_type = "month"
        value = date.today().strftime("%Y-%m")

    todo.reassign(timeline_type, value)

    if request.headers.get("HX-Request"):
        # Return empty to remove from current list (will appear in new section on refresh)
        return "", 200

    return jsonify(todo.to_dict())


@app.route("/api/todos/reorder", methods=["POST"])
def api_reorder_todos():
    """Reorder todos (for drag and drop)."""
    data = get_request_data()
    _ = data.get("order", [])  # List of todo IDs in new order (placeholder)

    # For now, we don't have a priority field, so this is a placeholder
    # Could add a 'priority' or 'sort_order' field to implement this

    if request.headers.get("HX-Request"):
        return "", 200
    return jsonify({"success": True})


@app.route("/api/tags", methods=["GET"])
def api_get_tags():
    """Get all tags with counts."""
    tags = Todo.get_all_tags()
    # Return as list of objects with color info
    result = [
        {"name": name, "count": count, "color": tag_color(name)}
        for name, count in tags.items()
    ]
    return jsonify(result)


@app.route("/api/sync", methods=["POST"])
def api_trigger_sync():
    """Manually trigger a sync."""
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.nightly_sync import run_sync
        result = run_sync()
        return jsonify(result)
    except ImportError as e:
        return jsonify({"error": f"Sync script not available: {e}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============== Suggestions API ==============

@app.route("/api/suggestions", methods=["GET"])
def api_get_suggestions():
    """Get all pending suggestions."""
    suggestions = Todo.get_suggestions()
    return jsonify([s.to_dict() for s in suggestions])


@app.route("/api/suggestions/<int:suggestion_id>/accept", methods=["POST"])
def api_accept_suggestion(suggestion_id: int):
    """Accept a suggestion and convert to todo."""
    suggestion = Todo.get_by_id(suggestion_id)
    if not suggestion or not suggestion.is_suggestion:
        return jsonify({"error": "Suggestion not found"}), 404

    data = get_request_data()
    timeline_type = data.get("timeline_type", "date")
    value = data.get("value")

    # Handle tags if provided
    if "tags" in data:
        tags_input = data["tags"]
        if isinstance(tags_input, str):
            suggestion.tags = [t.strip().lower() for t in tags_input.split(",") if t.strip()]
        else:
            suggestion.tags = [t.strip().lower() for t in tags_input if t.strip()]

    # Handle shortcuts
    if timeline_type == "today":
        timeline_type = "date"
        value = date.today().isoformat()
    elif timeline_type == "tomorrow":
        timeline_type = "date"
        value = (date.today() + timedelta(days=1)).isoformat()
    elif timeline_type == "this_week":
        timeline_type = "week"
        current_week = date.today().isocalendar()
        value = f"{current_week[0]}-W{current_week[1]:02d}"

    suggestion.accept_suggestion(timeline_type, value)

    if request.headers.get("HX-Request"):
        return "", 200  # Remove from suggestions list

    return jsonify(suggestion.to_dict())


@app.route("/api/suggestions/<int:suggestion_id>/discard", methods=["POST"])
def api_discard_suggestion(suggestion_id: int):
    """Discard a suggestion."""
    suggestion = Todo.get_by_id(suggestion_id)
    if not suggestion or not suggestion.is_suggestion:
        return jsonify({"error": "Suggestion not found"}), 404

    suggestion.discard_suggestion()

    if request.headers.get("HX-Request"):
        return "", 200  # Remove from suggestions list

    return jsonify({"success": True})


@app.route("/api/suggestions/cleanup", methods=["POST"])
def api_cleanup_suggestions():
    """Remove duplicate suggestions, keeping only the most recent."""
    token = request.headers.get("X-Deploy-Token") or request.args.get("token")
    if not DEPLOY_SECRET or token != DEPLOY_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    from digiman.models import get_db

    with get_db() as conn:
        # Find duplicates by title and source_type, keep the one with lowest ID
        cursor = conn.execute("""
            DELETE FROM todos
            WHERE is_suggestion = 1
            AND id NOT IN (
                SELECT MIN(id)
                FROM todos
                WHERE is_suggestion = 1
                GROUP BY title, source_type
            )
        """)
        deleted = cursor.rowcount
        conn.commit()

    return jsonify({"success": True, "deleted": deleted})


@app.route("/api/suggestions/import", methods=["POST"])
def api_import_suggestions():
    """Bulk import suggestions (for syncing from local to remote)."""
    # Verify deploy token for security
    token = request.headers.get("X-Deploy-Token") or request.args.get("token")
    if not DEPLOY_SECRET or token != DEPLOY_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    data = get_request_data()
    suggestions_data = data.get("suggestions", [])

    if not suggestions_data:
        return jsonify({"error": "No suggestions provided"}), 400

    imported = 0
    skipped = 0
    rejected = 0
    rejection_reasons = {}

    for item in suggestions_data:
        # Skip if already exists (by source_id)
        source_id = item.get("source_id")
        if source_id:
            from digiman.models import ProcessedSource
            if ProcessedSource.is_processed(item.get("source_type", "manual"), source_id):
                skipped += 1
                continue

        # Filter out non-actionable suggestions
        title = item.get("title", "")
        description = item.get("description", "")
        should_reject, reason = should_reject_suggestion(title, description)
        if should_reject:
            rejected += 1
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            # Still mark as processed so we don't try again
            if source_id:
                ProcessedSource.mark_processed(item.get("source_type", "manual"), source_id)
            continue

        todo = Todo(
            title=item.get("title", "Imported suggestion"),
            description=item.get("description"),
            source_type=item.get("source_type", "manual"),
            source_id=source_id,
            source_context=item.get("source_context"),
            source_url=item.get("source_url"),
            is_suggestion=True,
            extraction_confidence=item.get("extraction_confidence")
        )
        todo.save()

        # Mark as processed to avoid re-import
        if source_id:
            ProcessedSource.mark_processed(item.get("source_type", "manual"), source_id)

        imported += 1

    return jsonify({
        "success": True,
        "imported": imported,
        "skipped": skipped,
        "rejected": rejected,
        "rejection_reasons": rejection_reasons
    })


# ============== System Status ==============

# In-memory status storage (will be replaced by database in production)
_monitoring_status = {}

@app.route("/status")
def status_page():
    """System status dashboard (Monitoring tab)."""
    global _monitoring_status

    # Use synced status from API if available, otherwise try local file
    cron_status = _monitoring_status.copy() if _monitoring_status else {}

    # Fallback to local file (for local development)
    if not cron_status:
        from pathlib import Path
        status_file = Path.home() / ".digiman" / "cron_status.json"
        if status_file.exists():
            try:
                cron_status = json.loads(status_file.read_text())
            except (json.JSONDecodeError, ValueError, OSError):
                pass

    return render_template("status.html", cron_status=cron_status, active_page="status")


@app.route("/api/monitoring/status", methods=["GET"])
def api_get_monitoring_status():
    """Get current monitoring status."""
    global _monitoring_status
    return jsonify(_monitoring_status)


@app.route("/api/monitoring/status", methods=["POST"])
def api_update_monitoring_status():
    """Receive monitoring status update from local machine."""
    global _monitoring_status

    # Verify deploy token for security
    token = request.headers.get("X-Deploy-Token") or request.args.get("token")
    if not DEPLOY_SECRET or token != DEPLOY_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    data = get_request_data()

    # Merge the incoming status with existing
    # This allows partial updates
    if data:
        _monitoring_status.update(data)
        _monitoring_status["last_synced_from_local"] = date.today().isoformat()

    return jsonify({"success": True, "status": _monitoring_status})


# ============== HTMX Partials ==============

@app.route("/partials/todo-list")
def partial_todo_list():
    """Get the full todo list partial for today view."""
    todos = Todo.get_today()
    today = date.today()
    current_week = today.isocalendar()
    week_str = f"{current_week[0]}-W{current_week[1]:02d}"

    return render_template(
        "partials/todo_list.html",
        todos=todos,
        today=today,
        week_str=week_str
    )


@app.route("/partials/add-form")
def partial_add_form():
    """Get the add todo form partial."""
    return render_template("partials/add_form.html", today=date.today())


# ============== Deploy Webhook ==============

@app.route("/api/deploy", methods=["POST"])
def deploy_webhook():
    """Webhook to trigger git pull for deployment."""
    # Verify secret token
    token = request.headers.get("X-Deploy-Token") or request.args.get("token")
    if not DEPLOY_SECRET or token != DEPLOY_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        # Get the project root directory
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Run git pull
        result = subprocess.run(
            ["git", "pull"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=30
        )

        return jsonify({
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Git pull timed out"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=FLASK_DEBUG, port=5050)
