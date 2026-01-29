#!/usr/bin/env python3
"""Digiman Menu Bar App for macOS."""

import rumps
import requests
import webbrowser
import json
import os
from datetime import date, timedelta, datetime
from pathlib import Path

# Configuration
API_BASE = "https://manmohanbuildsproducts.pythonanywhere.com"
LOCAL_API = "http://localhost:5050"
STATUS_FILE = Path.home() / ".digiman" / "cron_status.json"


class DigimanMenuBar(rumps.App):
    def __init__(self):
        super().__init__("Digiman", title="🧠 0", quit_button=None)
        self.todos = []

        # Build initial menu structure
        self.menu = [
            rumps.MenuItem("Loading...", callback=None),
        ]

        # Initial load
        self.refresh_todos()

    def refresh_todos(self):
        """Fetch today's todos from the API."""
        try:
            response = requests.get(f"{API_BASE}/api/todos", timeout=5)
            if response.ok:
                all_todos = response.json()
                today = date.today().isoformat()
                self.todos = [
                    t for t in all_todos
                    if t.get("due_date") == today and t.get("status") == "pending"
                ]
        except Exception as e:
            print(f"Error fetching todos: {e}")
            self.todos = []

        self.rebuild_menu()

    def rebuild_menu(self):
        """Rebuild the menu with current todos."""
        self.menu.clear()
        count = len(self.todos)

        # Update title with count
        if count == 0:
            self.title = "🧠 ✓"
        else:
            self.title = f"🧠 {count}"

        # === HEADER ===
        if count == 0:
            self.menu.add(rumps.MenuItem("✓  All done for today!", callback=None))
        else:
            self.menu.add(rumps.MenuItem(f"TODAY ({count})", callback=None))
            self.menu.add(None)  # separator

            # === TODO ITEMS ===
            for todo in self.todos[:10]:
                title = todo['title']
                if len(title) > 55:
                    title = title[:55] + "..."

                # Add indicator if has description
                desc = todo.get('description')
                indicator = " 📝" if desc else ""

                item = rumps.MenuItem(
                    f"☐  {title}{indicator}",
                    callback=self.make_todo_callback(todo)
                )
                self.menu.add(item)

        # === ACTIONS ===
        self.menu.add(None)  # separator
        self.menu.add(rumps.MenuItem("➕  New Todo", callback=self.on_add_todo))
        self.menu.add(rumps.MenuItem("🔄  Refresh", callback=self.on_refresh))

        # === SYSTEM STATUS ===
        self.menu.add(None)  # separator
        status = self.get_cron_status()
        if status:
            last_sync = status.get("last_sync")
            if last_sync:
                try:
                    dt = datetime.fromisoformat(last_sync)
                    ago = self.time_ago(dt)
                    sync_status = status.get("last_sync_status", "unknown")
                    icon = "✅" if sync_status == "success" else "❌"
                    self.menu.add(rumps.MenuItem(f"{icon}  Last sync: {ago}", callback=None))
                except:
                    self.menu.add(rumps.MenuItem("⏳  No sync yet", callback=None))
            else:
                self.menu.add(rumps.MenuItem("⏳  No sync yet", callback=None))
        else:
            self.menu.add(rumps.MenuItem("⏳  No sync yet", callback=None))

        self.menu.add(rumps.MenuItem("⚙️  System Status", callback=self.on_open_status))
        self.menu.add(rumps.MenuItem("▶️  Run Sync Now", callback=self.on_run_sync))

        # === WEB ===
        self.menu.add(None)  # separator
        self.menu.add(rumps.MenuItem("🌐  Open Full App", callback=self.on_open_web))

    def make_todo_callback(self, todo):
        """Create callback for a todo item."""
        def callback(sender):
            self.show_todo_actions(todo)
        return callback

    def show_todo_actions(self, todo):
        """Show action dialog for a todo."""
        # Build message with description if available
        desc = todo.get('description')
        message = desc if desc else "What would you like to do?"

        response = rumps.alert(
            title=f"☐ {todo['title']}",
            message=message,
            ok="✓ Done",
            cancel="Cancel",
            other="→ Tomorrow"
        )

        if response == 1:  # OK = Complete
            self.complete_todo(todo['id'])
        elif response == 2:  # Other = Tomorrow
            self.move_to_tomorrow(todo['id'])

    def complete_todo(self, todo_id):
        """Mark todo as complete."""
        try:
            response = requests.post(f"{API_BASE}/api/todos/{todo_id}/toggle", timeout=5)
            if response.ok:
                rumps.notification("Digiman", "✓ Completed", "Nice work!")
                self.refresh_todos()
        except Exception as e:
            rumps.notification("Digiman", "Error", str(e))

    def move_to_tomorrow(self, todo_id):
        """Move todo to tomorrow."""
        try:
            tomorrow = (date.today() + timedelta(days=1)).isoformat()
            response = requests.post(
                f"{API_BASE}/api/todos/{todo_id}/reassign",
                json={"timeline_type": "date", "value": tomorrow},
                timeout=5
            )
            if response.ok:
                rumps.notification("Digiman", "→ Moved", "Rescheduled to tomorrow")
                self.refresh_todos()
        except Exception as e:
            rumps.notification("Digiman", "Error", str(e))

    def on_refresh(self, _):
        """Refresh todos."""
        self.refresh_todos()
        count = len(self.todos)
        msg = "All clear!" if count == 0 else f"{count} todo{'s' if count != 1 else ''}"
        rumps.notification("Digiman", "Refreshed", msg)

    def on_add_todo(self, _):
        """Add new todo."""
        window = rumps.Window(
            message="What do you need to do?",
            title="New Todo",
            default_text="",
            ok="Add",
            cancel="Cancel",
            dimensions=(320, 24)
        )
        response = window.run()

        if response.clicked and response.text.strip():
            try:
                result = requests.post(
                    f"{API_BASE}/api/todos",
                    json={"title": response.text.strip(), "due_date": date.today().isoformat()},
                    timeout=5
                )
                if result.ok:
                    rumps.notification("Digiman", "✓ Added", response.text.strip()[:30])
                    self.refresh_todos()
            except Exception as e:
                rumps.notification("Digiman", "Error", str(e))

    def on_open_web(self, _):
        """Open web UI."""
        webbrowser.open(API_BASE)

    def on_open_status(self, _):
        """Open local system status page."""
        webbrowser.open(f"{LOCAL_API}/status")

    def on_run_sync(self, _):
        """Manually trigger a sync."""
        try:
            rumps.notification("Digiman", "Starting sync...", "This may take a moment")
            response = requests.post(f"{LOCAL_API}/api/sync", timeout=60)
            if response.ok:
                result = response.json()
                count = result.get("new_todos", 0)
                rumps.notification("Digiman", "✅ Sync complete", f"{count} new action items")
                self.refresh_todos()
            else:
                rumps.notification("Digiman", "❌ Sync failed", response.text[:50])
        except requests.exceptions.ConnectionError:
            rumps.notification("Digiman", "❌ Local server not running", "Start with: python run.py")
        except Exception as e:
            rumps.notification("Digiman", "❌ Sync error", str(e)[:50])

    def get_cron_status(self):
        """Read cron status from file."""
        try:
            if STATUS_FILE.exists():
                return json.loads(STATUS_FILE.read_text())
        except:
            pass
        return None

    def time_ago(self, dt):
        """Convert datetime to human-readable 'time ago' string."""
        now = datetime.now()
        diff = now - dt
        seconds = diff.total_seconds()

        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            mins = int(seconds / 60)
            return f"{mins}m ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h ago"
        else:
            days = int(seconds / 86400)
            return f"{days}d ago"


if __name__ == "__main__":
    DigimanMenuBar().run()
