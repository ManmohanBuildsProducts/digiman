#!/usr/bin/env python3
"""Digiman Menu Bar App for macOS."""

import rumps
import requests
import webbrowser
from datetime import date, timedelta

# Configuration
API_BASE = "https://manmohanbuildsproducts.pythonanywhere.com"
# For local development, use: API_BASE = "http://localhost:5050"


class DigimanMenuBar(rumps.App):
    def __init__(self):
        super().__init__("Digiman", icon=None, title="📋")
        self.todos = []
        self.refresh_todos()

    def refresh_todos(self):
        """Fetch today's todos from the API."""
        try:
            response = requests.get(f"{API_BASE}/api/todos", timeout=5)
            if response.ok:
                all_todos = response.json()
                today = date.today().isoformat()
                # Filter for today's pending todos
                self.todos = [
                    t for t in all_todos
                    if t.get("due_date") == today and t.get("status") == "pending"
                ]
                self.update_menu()
        except Exception as e:
            print(f"Error fetching todos: {e}")
            self.todos = []
            self.update_menu()

    def update_menu(self):
        """Update the menu with current todos."""
        self.menu.clear()

        # Header
        count = len(self.todos)
        if count == 0:
            self.title = "✅"
            self.menu.add(rumps.MenuItem("No todos for today!", callback=None))
        else:
            self.title = f"📋 {count}"
            self.menu.add(rumps.MenuItem(f"Today's Todos ({count})", callback=None))
            self.menu.add(rumps.separator)

            # Add each todo
            for todo in self.todos[:10]:  # Limit to 10 items
                todo_item = rumps.MenuItem(
                    f"○ {todo['title'][:40]}{'...' if len(todo['title']) > 40 else ''}",
                    callback=self.create_todo_submenu(todo)
                )
                self.menu.add(todo_item)

        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("🔄 Refresh", callback=self.on_refresh))
        self.menu.add(rumps.MenuItem("➕ Add Todo...", callback=self.on_add_todo))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("🌐 Open Web UI", callback=self.on_open_web))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))

    def create_todo_submenu(self, todo):
        """Create a callback for todo item click - shows action window."""
        def callback(_):
            self.show_todo_actions(todo)
        return callback

    def show_todo_actions(self, todo):
        """Show action options for a todo."""
        response = rumps.alert(
            title=todo['title'],
            message=todo.get('description') or 'No description',
            ok="Complete ✓",
            cancel="Cancel",
            other="→ Tomorrow"
        )

        if response == 1:  # Complete
            self.complete_todo(todo['id'])
        elif response == 2:  # Tomorrow
            self.move_to_tomorrow(todo['id'])

    def complete_todo(self, todo_id):
        """Mark a todo as complete."""
        try:
            response = requests.post(
                f"{API_BASE}/api/todos/{todo_id}/toggle",
                timeout=5
            )
            if response.ok:
                rumps.notification("Digiman", "Todo completed!", "✓")
                self.refresh_todos()
        except Exception as e:
            rumps.notification("Digiman", "Error", str(e))

    def move_to_tomorrow(self, todo_id):
        """Move a todo to tomorrow."""
        try:
            tomorrow = (date.today() + timedelta(days=1)).isoformat()
            response = requests.post(
                f"{API_BASE}/api/todos/{todo_id}/reassign",
                json={"timeline_type": "date", "value": tomorrow},
                timeout=5
            )
            if response.ok:
                rumps.notification("Digiman", "Moved to tomorrow", "→")
                self.refresh_todos()
        except Exception as e:
            rumps.notification("Digiman", "Error", str(e))

    @rumps.clicked("🔄 Refresh")
    def on_refresh(self, _):
        """Refresh the todo list."""
        self.refresh_todos()
        rumps.notification("Digiman", "Refreshed", f"{len(self.todos)} todos today")

    @rumps.clicked("➕ Add Todo...")
    def on_add_todo(self, _):
        """Add a new todo via dialog."""
        window = rumps.Window(
            message="Enter todo title:",
            title="Add Todo",
            default_text="",
            ok="Add",
            cancel="Cancel",
            dimensions=(300, 24)
        )
        response = window.run()

        if response.clicked and response.text.strip():
            try:
                result = requests.post(
                    f"{API_BASE}/api/todos",
                    json={
                        "title": response.text.strip(),
                        "due_date": date.today().isoformat()
                    },
                    timeout=5
                )
                if result.ok:
                    rumps.notification("Digiman", "Todo added!", response.text.strip())
                    self.refresh_todos()
            except Exception as e:
                rumps.notification("Digiman", "Error", str(e))

    @rumps.clicked("🌐 Open Web UI")
    def on_open_web(self, _):
        """Open the web UI in browser."""
        webbrowser.open(API_BASE)


def main():
    DigimanMenuBar().run()


if __name__ == "__main__":
    main()
