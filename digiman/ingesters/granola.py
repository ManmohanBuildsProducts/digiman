"""Granola meeting notes ingester."""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from html.parser import HTMLParser

from digiman.config import GRANOLA_CACHE_PATH
from digiman.models import ProcessedSource


class HTMLTextExtractor(HTMLParser):
    """Extract plain text from HTML."""

    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.in_li = False

    def handle_starttag(self, tag, attrs):
        if tag == 'li':
            self.in_li = True
            self.text_parts.append('\n- ')
        elif tag in ('h1', 'h2', 'h3', 'h4', 'p'):
            self.text_parts.append('\n')

    def handle_endtag(self, tag):
        if tag == 'li':
            self.in_li = False
        elif tag in ('h1', 'h2', 'h3', 'h4', 'p', 'ul', 'ol'):
            self.text_parts.append('\n')

    def handle_data(self, data):
        self.text_parts.append(data)

    def get_text(self) -> str:
        return ''.join(self.text_parts).strip()


def html_to_text(html: str) -> str:
    """Convert HTML to plain text."""
    parser = HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


def tiptap_to_text(content: Any) -> str:
    """Convert TipTap/ProseMirror content to plain text."""
    try:
        if content is None:
            return ''

        if isinstance(content, str):
            return content

        if isinstance(content, dict):
            if content.get('type') == 'text':
                return str(content.get('text', ''))
            elif 'content' in content:
                return tiptap_to_text(content['content'])
            return ''

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    item_type = item.get('type', '')
                    text = tiptap_to_text(item.get('content', []))

                    # Ensure text is a string
                    if not isinstance(text, str):
                        text = str(text) if text else ''

                    if item_type == 'paragraph':
                        parts.append(text + '\n')
                    elif item_type == 'heading':
                        parts.append('\n' + text + '\n')
                    elif item_type == 'bulletList' or item_type == 'orderedList':
                        parts.append(text)
                    elif item_type == 'listItem':
                        parts.append('- ' + text + '\n')
                    elif item_type == 'text':
                        parts.append(str(item.get('text', '')))
                    else:
                        parts.append(text)
                elif isinstance(item, str):
                    parts.append(item)
            return ''.join(parts)

        return str(content) if content else ''
    except Exception as e:
        return ''


class GranolaIngester:
    """Parse Granola cache and extract meeting notes."""

    def __init__(self, cache_path: Optional[str] = None):
        self.cache_path = Path(cache_path or GRANOLA_CACHE_PATH).expanduser()

    def _load_cache(self) -> Dict[str, Any]:
        """Load and parse the double-JSON cache format."""
        if not self.cache_path.exists():
            print(f"⚠️  Granola cache not found at: {self.cache_path}")
            return {}

        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                outer_data = json.load(f)

            # The cache is JSON inside JSON
            cache_str = outer_data.get("cache", "{}")
            cache_data = json.loads(cache_str)
            return cache_data.get("state", {})

        except json.JSONDecodeError as e:
            print(f"⚠️  Error parsing Granola cache: {e}")
            return {}

    def get_recent_meetings(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get meetings from the last N hours."""
        state = self._load_cache()
        if not state:
            return []

        # Documents is a dict with doc_id as key
        documents = state.get("documents", {})
        panels = state.get("documentPanels", {})

        # Calculate cutoff time
        cutoff = datetime.now() - timedelta(hours=hours)

        meetings = []

        for doc_id, doc in documents.items():
            # Skip if already processed
            if ProcessedSource.is_processed("granola", doc_id):
                continue

            # Check if within time window
            created_at = doc.get("created_at")
            if not created_at:
                continue

            try:
                doc_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                doc_time = doc_time.replace(tzinfo=None)

                if doc_time < cutoff:
                    continue
            except (ValueError, TypeError) as e:
                continue

            # Skip deleted docs
            if doc.get("deleted_at"):
                continue

            # Extract notes text
            notes = doc.get("notes", {})
            notes_text = ""
            if isinstance(notes, dict):
                notes_text = tiptap_to_text(notes.get("content", []))
            elif isinstance(notes, str):
                notes_text = notes

            # Get summary from panels
            summary_text = ""
            doc_panels = panels.get(doc_id, {})
            for panel_id, panel in doc_panels.items():
                if panel.get("title") == "Summary":
                    content = panel.get("content", "")
                    if content:
                        # Content can be HTML string or TipTap dict
                        if isinstance(content, str):
                            summary_text = html_to_text(content)
                        elif isinstance(content, dict):
                            summary_text = tiptap_to_text(content.get("content", []))
                    break

            # Extract action-item-like lines from summary
            action_items = self._extract_action_items(summary_text)

            meeting = {
                "id": doc_id,
                "title": doc.get("title") or "Untitled Meeting",
                "created_at": created_at,
                "notes_text": notes_text,
                "summary_text": summary_text,
                "action_items": action_items,
                "url": None,  # Granola doesn't seem to have public URLs
            }

            meetings.append(meeting)

        return meetings

    def _extract_action_items(self, text: str) -> List[str]:
        """Extract action-item-like lines from text.

        Looks for patterns like:
        - Lines starting with action verbs followed by content
        - Lines containing "need to", "should", "must", "will"
        """
        if not text:
            return []

        # Skip these generic headings/phrases
        skip_patterns = [
            r'^(next steps?|action items?|tasks?|summary|overview|key points?|takeaways?)$',
            r'^(conclusion|discussion|notes?|agenda|attendees?)$',
        ]

        # Match action-like patterns
        action_patterns = [
            # Action verbs with actual content after them
            r'^-?\s*(Send|Review|Check|Confirm|Schedule|Call|Email|Create|Update|Fix|Complete|Prepare|Share|Follow up|Discuss|Finalize|Approve|Submit|Test|Deploy|Document|Implement)\s+\S.{5,}',
            # Lines with modal verbs indicating action
            r'^-?\s*\S.{5,}(?:need to|should|must|will|going to)\s+\S.{3,}',
            # Explicit TODO markers
            r'^-?\s*(?:TODO|Action item|Task)[:.]?\s+\S.{5,}',
        ]

        items = []
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line or len(line) < 15:  # Minimum length for meaningful action
                continue

            # Skip generic headings
            clean_line = line.lstrip('- ').strip()
            skip = False
            for skip_pat in skip_patterns:
                if re.match(skip_pat, clean_line, re.IGNORECASE):
                    skip = True
                    break
            if skip:
                continue

            # Check for action patterns
            for pattern in action_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    item = line.lstrip('- ')
                    if item and item not in items:
                        items.append(item)
                    break

        return items[:10]  # Max 10 action items per meeting

    def get_content_for_extraction(self, meeting: Dict[str, Any]) -> str:
        """Get the best content from a meeting for display/extraction."""
        parts = []

        if meeting.get("title"):
            parts.append(f"Meeting: {meeting['title']}")
            parts.append("")

        if meeting.get("summary_text"):
            parts.append("## Summary")
            parts.append(meeting["summary_text"])
            parts.append("")

        if meeting.get("notes_text"):
            parts.append("## Notes")
            parts.append(meeting["notes_text"][:2000])  # Limit notes
            parts.append("")

        return "\n".join(parts)

    def mark_processed(self, meeting_id: str):
        """Mark a meeting as processed."""
        ProcessedSource.mark_processed("granola", meeting_id)
