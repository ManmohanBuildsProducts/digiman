"""Todo model and database operations."""

import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from digiman.config import DATABASE_PATH


def get_db_path() -> Path:
    """Get the database path, creating parent directories if needed."""
    path = Path(DATABASE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize the database schema."""
    with get_db() as conn:
        conn.executescript("""
            -- Core todo items
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                source_type TEXT NOT NULL,  -- 'granola' | 'slack' | 'manual'
                source_id TEXT,             -- Meeting ID or Slack thread ID
                source_context TEXT,        -- Meeting title or channel name
                source_url TEXT,            -- Link to original

                -- Timeline fields
                timeline_type TEXT NOT NULL DEFAULT 'date',  -- 'date' | 'week' | 'month' | 'backlog'
                due_date DATE,              -- Specific date (if timeline_type = 'date')
                due_week TEXT,              -- ISO week like '2026-W05' (if timeline_type = 'week')
                due_month TEXT,             -- Month like '2026-01' (if timeline_type = 'month')

                -- Status
                status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'completed' | 'deferred'
                is_overdue BOOLEAN DEFAULT FALSE,
                days_overdue INTEGER DEFAULT 0,

                -- Suggestion flag (items from sync that need user approval)
                is_suggestion BOOLEAN DEFAULT FALSE,

                -- Metadata
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,

                -- AI extraction confidence
                extraction_confidence REAL  -- 0.0 to 1.0
            );

            -- Track sync history
            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_type TEXT NOT NULL,    -- 'granola' | 'slack' | 'full'
                started_at DATETIME,
                completed_at DATETIME,
                items_processed INTEGER,
                items_extracted INTEGER,
                errors TEXT
            );

            -- Track processed sources to avoid duplicates
            CREATE TABLE IF NOT EXISTS processed_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_type, source_id)
            );

            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
            CREATE INDEX IF NOT EXISTS idx_todos_due_date ON todos(due_date);
            CREATE INDEX IF NOT EXISTS idx_todos_timeline_type ON todos(timeline_type);
            CREATE INDEX IF NOT EXISTS idx_processed_sources_lookup ON processed_sources(source_type, source_id);
        """)
        conn.commit()

        # Run migrations for existing databases
        _run_migrations(conn)


def _run_migrations(conn):
    """Run schema migrations for existing databases."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(todos)")
    columns = [col[1] for col in cursor.fetchall()]

    # Migration: Add is_suggestion column if it doesn't exist
    if "is_suggestion" not in columns:
        cursor.execute("ALTER TABLE todos ADD COLUMN is_suggestion BOOLEAN DEFAULT FALSE")
        conn.commit()


class Todo:
    """Todo item model."""

    def __init__(self, row: Optional[sqlite3.Row] = None, **kwargs):
        if row:
            self._load_from_row(row)
        else:
            self.id = kwargs.get("id")
            self.title = kwargs.get("title", "")
            self.description = kwargs.get("description")
            self.source_type = kwargs.get("source_type", "manual")
            self.source_id = kwargs.get("source_id")
            self.source_context = kwargs.get("source_context")
            self.source_url = kwargs.get("source_url")
            self.timeline_type = kwargs.get("timeline_type", "date")
            self.due_date = kwargs.get("due_date")
            self.due_week = kwargs.get("due_week")
            self.due_month = kwargs.get("due_month")
            self.status = kwargs.get("status", "pending")
            self.is_overdue = kwargs.get("is_overdue", False)
            self.days_overdue = kwargs.get("days_overdue", 0)
            self.is_suggestion = kwargs.get("is_suggestion", False)
            self.created_at = kwargs.get("created_at")
            self.updated_at = kwargs.get("updated_at")
            self.completed_at = kwargs.get("completed_at")
            self.extraction_confidence = kwargs.get("extraction_confidence")

    def _load_from_row(self, row: sqlite3.Row):
        """Load data from database row."""
        self.id = row["id"]
        self.title = row["title"]
        self.description = row["description"]
        self.source_type = row["source_type"]
        self.source_id = row["source_id"]
        self.source_context = row["source_context"]
        self.source_url = row["source_url"]
        self.timeline_type = row["timeline_type"]
        self.due_date = row["due_date"]
        self.due_week = row["due_week"]
        self.due_month = row["due_month"]
        self.status = row["status"]
        self.is_overdue = bool(row["is_overdue"])
        self.days_overdue = row["days_overdue"]
        self.is_suggestion = bool(row["is_suggestion"]) if "is_suggestion" in row.keys() else False
        self.created_at = row["created_at"]
        self.updated_at = row["updated_at"]
        self.completed_at = row["completed_at"]
        self.extraction_confidence = row["extraction_confidence"]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "source_context": self.source_context,
            "source_url": self.source_url,
            "timeline_type": self.timeline_type,
            "due_date": self.due_date,
            "due_week": self.due_week,
            "due_month": self.due_month,
            "status": self.status,
            "is_overdue": self.is_overdue,
            "days_overdue": self.days_overdue,
            "is_suggestion": self.is_suggestion,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "extraction_confidence": self.extraction_confidence,
        }

    def save(self) -> int:
        """Save todo to database. Returns the ID."""
        with get_db() as conn:
            if self.id:
                conn.execute("""
                    UPDATE todos SET
                        title = ?, description = ?, source_type = ?, source_id = ?,
                        source_context = ?, source_url = ?, timeline_type = ?,
                        due_date = ?, due_week = ?, due_month = ?, status = ?,
                        is_overdue = ?, days_overdue = ?, is_suggestion = ?, updated_at = ?,
                        completed_at = ?, extraction_confidence = ?
                    WHERE id = ?
                """, (
                    self.title, self.description, self.source_type, self.source_id,
                    self.source_context, self.source_url, self.timeline_type,
                    self.due_date, self.due_week, self.due_month, self.status,
                    self.is_overdue, self.days_overdue, self.is_suggestion, datetime.now().isoformat(),
                    self.completed_at, self.extraction_confidence, self.id
                ))
            else:
                cursor = conn.execute("""
                    INSERT INTO todos (
                        title, description, source_type, source_id, source_context,
                        source_url, timeline_type, due_date, due_week, due_month,
                        status, is_overdue, days_overdue, is_suggestion, extraction_confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.title, self.description, self.source_type, self.source_id,
                    self.source_context, self.source_url, self.timeline_type,
                    self.due_date, self.due_week, self.due_month, self.status,
                    self.is_overdue, self.days_overdue, self.is_suggestion, self.extraction_confidence
                ))
                self.id = cursor.lastrowid
            conn.commit()
        return self.id

    def complete(self):
        """Mark todo as completed."""
        self.status = "completed"
        self.completed_at = datetime.now().isoformat()
        self.is_overdue = False
        self.days_overdue = 0
        self.save()

    def uncomplete(self):
        """Mark todo as pending."""
        self.status = "pending"
        self.completed_at = None
        self._update_overdue_status()
        self.save()

    def _update_overdue_status(self):
        """Update is_overdue and days_overdue based on due_date."""
        if self.timeline_type == "date" and self.due_date:
            due = date.fromisoformat(self.due_date) if isinstance(self.due_date, str) else self.due_date
            today = date.today()
            if due < today:
                self.is_overdue = True
                self.days_overdue = (today - due).days
            else:
                self.is_overdue = False
                self.days_overdue = 0

    def reassign(self, timeline_type: str, value: Optional[str] = None):
        """Reassign todo to a different timeline."""
        self.timeline_type = timeline_type
        self.due_date = None
        self.due_week = None
        self.due_month = None

        if timeline_type == "date" and value:
            self.due_date = value
        elif timeline_type == "week" and value:
            self.due_week = value
        elif timeline_type == "month" and value:
            self.due_month = value

        self._update_overdue_status()
        self.save()

    @classmethod
    def get_by_id(cls, todo_id: int) -> Optional["Todo"]:
        """Get todo by ID."""
        with get_db() as conn:
            row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
            return cls(row=row) if row else None

    @classmethod
    def get_all(cls, status: Optional[str] = None) -> List["Todo"]:
        """Get all todos, optionally filtered by status."""
        with get_db() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM todos WHERE status = ? ORDER BY due_date ASC, created_at DESC",
                    (status,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM todos ORDER BY due_date ASC, created_at DESC"
                ).fetchall()
            return [cls(row=row) for row in rows]

    @classmethod
    def get_today(cls) -> Dict[str, List["Todo"]]:
        """Get todos for today view, grouped by category."""
        today = date.today().isoformat()
        current_week = date.today().isocalendar()
        week_str = f"{current_week[0]}-W{current_week[1]:02d}"

        with get_db() as conn:
            # Update overdue status for all pending todos
            conn.execute("""
                UPDATE todos SET
                    is_overdue = CASE
                        WHEN timeline_type = 'date' AND due_date < ? AND status = 'pending' THEN 1
                        ELSE 0
                    END,
                    days_overdue = CASE
                        WHEN timeline_type = 'date' AND due_date < ? AND status = 'pending'
                        THEN julianday(?) - julianday(due_date)
                        ELSE 0
                    END
                WHERE status = 'pending'
            """, (today, today, today))
            conn.commit()

            # Get overdue (exclude suggestions)
            overdue_rows = conn.execute("""
                SELECT * FROM todos
                WHERE is_overdue = 1 AND status = 'pending'
                AND (is_suggestion = 0 OR is_suggestion IS NULL)
                ORDER BY due_date ASC
            """).fetchall()

            # Get today's todos (exclude suggestions)
            today_rows = conn.execute("""
                SELECT * FROM todos
                WHERE timeline_type = 'date' AND due_date = ? AND status = 'pending'
                AND (is_suggestion = 0 OR is_suggestion IS NULL)
                ORDER BY created_at DESC
            """, (today,)).fetchall()

            # Get this week's todos (exclude suggestions)
            week_rows = conn.execute("""
                SELECT * FROM todos
                WHERE timeline_type = 'week' AND due_week = ? AND status = 'pending'
                AND (is_suggestion = 0 OR is_suggestion IS NULL)
                ORDER BY created_at DESC
            """, (week_str,)).fetchall()

            # Get completed today
            completed_rows = conn.execute("""
                SELECT * FROM todos
                WHERE status = 'completed' AND DATE(completed_at) = ?
                ORDER BY completed_at DESC
            """, (today,)).fetchall()

        return {
            "overdue": [cls(row=row) for row in overdue_rows],
            "today": [cls(row=row) for row in today_rows],
            "this_week": [cls(row=row) for row in week_rows],
            "completed": [cls(row=row) for row in completed_rows],
        }

    @classmethod
    def get_calendar_data(cls, year: int, month: int) -> Dict[str, Any]:
        """Get todos grouped by date for calendar view."""
        month_str = f"{year}-{month:02d}"

        with get_db() as conn:
            # Get todos with specific dates in this month
            date_rows = conn.execute("""
                SELECT * FROM todos
                WHERE timeline_type = 'date'
                AND strftime('%Y-%m', due_date) = ?
                ORDER BY due_date ASC, created_at DESC
            """, (month_str,)).fetchall()

            # Get weekly todos for weeks in this month
            week_rows = conn.execute("""
                SELECT * FROM todos
                WHERE timeline_type = 'week'
                AND due_week LIKE ?
                ORDER BY due_week ASC, created_at DESC
            """, (f"{year}-W%",)).fetchall()

            # Get monthly todos
            month_rows = conn.execute("""
                SELECT * FROM todos
                WHERE timeline_type = 'month' AND due_month = ?
                ORDER BY created_at DESC
            """, (month_str,)).fetchall()

            # Get backlog
            backlog_rows = conn.execute("""
                SELECT * FROM todos
                WHERE timeline_type = 'backlog' AND status = 'pending'
                ORDER BY created_at DESC
            """).fetchall()

        # Group by date
        by_date = {}
        for row in date_rows:
            todo = cls(row=row)
            if todo.due_date not in by_date:
                by_date[todo.due_date] = []
            by_date[todo.due_date].append(todo)

        return {
            "by_date": by_date,
            "weekly": [cls(row=row) for row in week_rows],
            "monthly": [cls(row=row) for row in month_rows],
            "backlog": [cls(row=row) for row in backlog_rows],
        }

    @classmethod
    def delete(cls, todo_id: int) -> bool:
        """Delete a todo by ID."""
        with get_db() as conn:
            cursor = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
            conn.commit()
            return cursor.rowcount > 0

    @classmethod
    def get_suggestions(cls) -> List["Todo"]:
        """Get all pending suggestions (not yet accepted as todos)."""
        with get_db() as conn:
            rows = conn.execute("""
                SELECT * FROM todos
                WHERE is_suggestion = 1 AND status = 'pending'
                ORDER BY created_at DESC
            """).fetchall()
            return [cls(row=row) for row in rows]

    def accept_suggestion(self, timeline_type: str, value: Optional[str] = None):
        """Accept a suggestion and convert it to a real todo.

        Args:
            timeline_type: 'date', 'week', or 'backlog'
            value: The date (YYYY-MM-DD) or week (YYYY-Wxx) value
        """
        self.is_suggestion = False
        self.timeline_type = timeline_type
        self.due_date = None
        self.due_week = None
        self.due_month = None

        if timeline_type == "date" and value:
            self.due_date = value
        elif timeline_type == "week" and value:
            self.due_week = value

        self._update_overdue_status()
        self.save()

    def discard_suggestion(self):
        """Discard a suggestion (mark as completed/discarded)."""
        self.status = "discarded"
        self.is_suggestion = False
        self.save()


class SyncHistory:
    """Track sync operations."""

    @classmethod
    def start(cls, sync_type: str) -> int:
        """Start a sync operation, return the ID."""
        with get_db() as conn:
            cursor = conn.execute("""
                INSERT INTO sync_history (sync_type, started_at)
                VALUES (?, ?)
            """, (sync_type, datetime.now().isoformat()))
            conn.commit()
            return cursor.lastrowid

    @classmethod
    def complete(cls, sync_id: int, items_processed: int, items_extracted: int, errors: Optional[str] = None):
        """Mark sync as complete."""
        with get_db() as conn:
            conn.execute("""
                UPDATE sync_history SET
                    completed_at = ?,
                    items_processed = ?,
                    items_extracted = ?,
                    errors = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), items_processed, items_extracted, errors, sync_id))
            conn.commit()


class ProcessedSource:
    """Track processed sources to avoid duplicates."""

    @classmethod
    def is_processed(cls, source_type: str, source_id: str) -> bool:
        """Check if a source has been processed."""
        with get_db() as conn:
            row = conn.execute("""
                SELECT 1 FROM processed_sources
                WHERE source_type = ? AND source_id = ?
            """, (source_type, source_id)).fetchone()
            return row is not None

    @classmethod
    def mark_processed(cls, source_type: str, source_id: str):
        """Mark a source as processed."""
        with get_db() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO processed_sources (source_type, source_id)
                VALUES (?, ?)
            """, (source_type, source_id))
            conn.commit()
