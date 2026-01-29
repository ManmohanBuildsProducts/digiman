"""Flask application for Digiman."""

from datetime import date, datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for
import calendar
import json

import os
import subprocess
from digiman.config import FLASK_SECRET_KEY, FLASK_DEBUG

# Deploy webhook secret (set in environment)
DEPLOY_SECRET = os.getenv("DEPLOY_SECRET", "")
from digiman.models import Todo, init_db

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY


def get_request_data():
    """Get data from request, handling both JSON and form data."""
    if request.is_json:
        return request.get_json(force=True, silent=True) or {}
    elif request.form:
        return request.form.to_dict()
    elif request.data:
        try:
            return json.loads(request.data)
        except:
            pass
    return {}


@app.before_request
def ensure_db():
    """Ensure database is initialized before any request."""
    init_db()


# ============== Page Routes ==============

@app.route("/")
def index():
    """Today view - main dashboard."""
    todos = Todo.get_today()
    today = date.today()
    current_week = today.isocalendar()
    week_str = f"{current_week[0]}-W{current_week[1]:02d}"

    return render_template(
        "index.html",
        todos=todos,
        today=today,
        week_str=week_str,
        active_page="today"
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

    todo = Todo(
        title=title,
        description=data.get("description"),
        source_type="manual",
        timeline_type=data.get("timeline_type", "date"),
        due_date=data.get("due_date") or date.today().isoformat(),
        due_week=data.get("due_week"),
        due_month=data.get("due_month"),
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

    if "title" in data:
        todo.title = data["title"]
    if "description" in data:
        todo.description = data["description"]
    if "status" in data:
        if data["status"] == "completed":
            todo.complete()
        else:
            todo.status = data["status"]
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
    order = data.get("order", [])  # List of todo IDs in new order

    # For now, we don't have a priority field, so this is a placeholder
    # Could add a 'priority' or 'sort_order' field to implement this

    if request.headers.get("HX-Request"):
        return "", 200
    return jsonify({"success": True})


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


# ============== System Status ==============

@app.route("/status")
def status_page():
    """System status dashboard."""
    from pathlib import Path

    status_file = Path.home() / ".digiman" / "cron_status.json"
    cron_status = {}
    if status_file.exists():
        try:
            cron_status = json.loads(status_file.read_text())
        except:
            pass

    return render_template("status.html", cron_status=cron_status, active_page="status")


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
