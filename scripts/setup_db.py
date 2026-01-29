#!/usr/bin/env python3
"""Initialize the Digiman database."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from digiman.models import init_db, get_db
from digiman.config import DATABASE_PATH


def main():
    """Initialize the database and show status."""
    print("🧠 Digiman Database Setup")
    print("=" * 40)
    print(f"Database path: {DATABASE_PATH}")

    # Initialize
    print("\nInitializing database...")
    init_db()

    # Verify
    with get_db() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t["name"] for t in tables]

    print(f"\n✅ Database initialized successfully!")
    print(f"   Tables created: {', '.join(table_names)}")

    # Show counts
    with get_db() as conn:
        todo_count = conn.execute("SELECT COUNT(*) as c FROM todos").fetchone()["c"]
        sync_count = conn.execute("SELECT COUNT(*) as c FROM sync_history").fetchone()["c"]
        source_count = conn.execute("SELECT COUNT(*) as c FROM processed_sources").fetchone()["c"]

    print(f"\nCurrent data:")
    print(f"   Todos: {todo_count}")
    print(f"   Sync history: {sync_count}")
    print(f"   Processed sources: {source_count}")


if __name__ == "__main__":
    main()
