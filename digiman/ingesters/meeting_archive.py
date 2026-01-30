"""Meeting Archive Ingester - reads ACTION ITEMS from SMART_PASTE processed files."""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from digiman.models import ProcessedSource

# Default path to MyNotes meeting archive
MEETING_ARCHIVE_PATH = Path.home() / "Downloads/MyNotes/02_Active_Projects/meeting_archive"


class MeetingArchiveIngester:
    """Parse processed meeting files and extract structured ACTION ITEMS."""

    def __init__(self, archive_path: Optional[str] = None):
        self.archive_path = Path(archive_path) if archive_path else MEETING_ARCHIVE_PATH

    def get_recent_meetings(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get processed meeting files from the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        meetings = []

        # Check current year directory
        year_dir = self.archive_path / str(datetime.now().year)
        if not year_dir.exists():
            return []

        for filepath in year_dir.glob("*.md"):
            # Skip index files
            if filepath.name.startswith("_") or "INDEX" in filepath.name:
                continue

            # Check modification time
            mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
            if mtime < cutoff:
                continue

            # Generate unique ID from filepath
            source_id = f"archive_{filepath.stem}"

            # Skip if already processed
            if ProcessedSource.is_processed("meeting_archive", source_id):
                continue

            # Parse the file
            content = filepath.read_text()
            meeting = self._parse_meeting_file(filepath, content, source_id)

            if meeting:
                meetings.append(meeting)

        return meetings

    def _parse_meeting_file(
        self, filepath: Path, content: str, source_id: str
    ) -> Optional[Dict[str, Any]]:
        """Parse a processed meeting file."""

        # Extract title from first heading or filename
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else filepath.stem.replace("-", " ").title()

        # Extract date from filename (YYYY-MM-DD_title.md)
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', filepath.name)
        meeting_date = date_match.group(1) if date_match else None

        # Extract ACTION ITEMS section
        action_items = self._extract_action_items(content)

        if not action_items:
            return None

        return {
            "id": source_id,
            "title": title,
            "date": meeting_date,
            "filepath": str(filepath),
            "action_items": action_items,
            "content": content,
        }

    def _extract_action_items(self, content: str) -> List[Dict[str, Any]]:
        """Extract structured action items from meeting content."""
        items = []

        # Find ACTION ITEMS section
        action_section_match = re.search(
            r'##\s*ACTION ITEMS.*?\n(.*?)(?=\n##|\Z)',
            content,
            re.IGNORECASE | re.DOTALL
        )

        if not action_section_match:
            # Try alternative format
            action_section_match = re.search(
                r'\*\*Action Items?\*\*.*?\n(.*?)(?=\n##|\n\*\*|\Z)',
                content,
                re.IGNORECASE | re.DOTALL
            )

        if action_section_match:
            action_text = action_section_match.group(1)

            # Parse structured format: Owner: X | Task: Y | Due: Z | Context: W
            structured_pattern = r'Owner:\s*([^|]+)\|?\s*Task:\s*([^|]+)(?:\|?\s*Due:\s*([^|]+))?(?:\|?\s*Context:\s*(.+))?'

            for match in re.finditer(structured_pattern, action_text, re.IGNORECASE):
                owner = match.group(1).strip() if match.group(1) else None
                task = match.group(2).strip() if match.group(2) else None
                due = match.group(3).strip() if match.group(3) else None
                context = match.group(4).strip() if match.group(4) else None

                if task:
                    items.append({
                        "title": task,
                        "owner": owner,
                        "due": due,
                        "context": context,
                        "confidence": 0.95  # High confidence from structured extraction
                    })

            # Also try bullet point format: - [action] Task description
            bullet_pattern = r'-\s*(?:\[action\])?\s*(.+?)(?:\n|$)'
            for match in re.finditer(bullet_pattern, action_text):
                line = match.group(1).strip()
                # Skip if already captured in structured format
                if any(item["title"] in line or line in item["title"] for item in items):
                    continue
                # Skip non-actionable lines
                if len(line) < 10 or line.startswith("#"):
                    continue

                items.append({
                    "title": line[:100],
                    "owner": None,
                    "due": None,
                    "context": None,
                    "confidence": 0.8
                })

        return items

    def get_content_for_extraction(self, meeting: Dict[str, Any]) -> str:
        """Get formatted content for display."""
        parts = [f"Meeting: {meeting['title']}"]

        if meeting.get("date"):
            parts.append(f"Date: {meeting['date']}")

        parts.append("")
        parts.append("## Action Items")

        for item in meeting.get("action_items", []):
            line = f"- {item['title']}"
            if item.get("owner"):
                line += f" (Owner: {item['owner']})"
            if item.get("due"):
                line += f" [Due: {item['due']}]"
            parts.append(line)

        return "\n".join(parts)

    def mark_processed(self, meeting_id: str):
        """Mark a meeting as processed."""
        ProcessedSource.mark_processed("meeting_archive", meeting_id)
