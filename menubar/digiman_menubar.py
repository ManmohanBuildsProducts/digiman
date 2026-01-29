#!/usr/bin/env python3
"""Digiman Menu Bar App for macOS - Todo management only."""

import rumps
import requests
import webbrowser
from datetime import date, timedelta

# Configuration
API_BASE = "https://manmohanbuildsproducts.pythonanywhere.com"


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


if __name__ == "__main__":
    DigimanMenuBar().run()
