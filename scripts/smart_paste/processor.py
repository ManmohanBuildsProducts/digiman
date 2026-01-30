#!/usr/bin/env python3
"""
SMART_PASTE Processor - Nightly cron to process Granola transcripts.

This replicates the Cursor SMART_PASTE ecosystem:
1. Reads raw Granola cache
2. Uses Claude Sonnet with full context (memory bank, business context)
3. Applies adaptive theme extraction
4. Saves structured meeting notes to meeting_archive
5. Updates MEETING_INDEX.md
"""

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import anthropic

# Configuration
GRANOLA_CACHE_PATH = Path.home() / "Library/Application Support/Granola/cache-v3.json"
MYNOTES_PATH = Path.home() / "Downloads/MyNotes"
MEETING_ARCHIVE_PATH = MYNOTES_PATH / "02_Active_Projects/meeting_archive"
MEMORY_BANK_PATH = MYNOTES_PATH / "memory-bank"
PROCESSED_LOG_PATH = Path.home() / ".digiman/smart_paste_processed.json"

# Ensure directories exist
PROCESSED_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_memory_bank() -> str:
    """Load relevant memory bank files for context."""
    context_parts = []

    key_files = [
        "business_context.md",
        "current_priorities.md",
        "working_patterns.md",
    ]

    for filename in key_files:
        filepath = MEMORY_BANK_PATH / filename
        if filepath.exists():
            content = filepath.read_text()[:3000]  # Limit each file
            context_parts.append(f"## {filename}\n{content}")

    return "\n\n".join(context_parts)


def load_smart_paste_template() -> str:
    """Load the SMART_PASTE output template."""
    template_path = MYNOTES_PATH / "01_Context/templates/meeting_notes/TEMPLATE_SMART_PASTE_Output.md"
    if template_path.exists():
        return template_path.read_text()[:2000]
    return ""


def get_processed_meetings() -> set:
    """Get set of already processed meeting IDs."""
    if PROCESSED_LOG_PATH.exists():
        try:
            data = json.loads(PROCESSED_LOG_PATH.read_text())
            return set(data.get("processed", []))
        except:
            pass
    return set()


def mark_meeting_processed(meeting_id: str):
    """Mark a meeting as processed."""
    processed = get_processed_meetings()
    processed.add(meeting_id)
    PROCESSED_LOG_PATH.write_text(json.dumps({
        "processed": list(processed),
        "last_updated": datetime.now().isoformat()
    }, indent=2))


def load_granola_cache() -> Dict[str, Any]:
    """Load and parse the Granola cache."""
    if not GRANOLA_CACHE_PATH.exists():
        print(f"⚠️  Granola cache not found at: {GRANOLA_CACHE_PATH}")
        return {}

    try:
        with open(GRANOLA_CACHE_PATH, "r", encoding="utf-8") as f:
            outer_data = json.load(f)

        cache_str = outer_data.get("cache", "{}")
        cache_data = json.loads(cache_str)
        return cache_data.get("state", {})
    except Exception as e:
        print(f"⚠️  Error parsing Granola cache: {e}")
        return {}


def extract_transcript_text(doc: Dict, panels: Dict) -> str:
    """Extract full transcript text from a Granola document."""
    parts = []

    # Get notes
    notes = doc.get("notes", {})
    if isinstance(notes, dict) and "content" in notes:
        parts.append(tiptap_to_text(notes.get("content", [])))
    elif isinstance(notes, str):
        parts.append(notes)

    # Get all panels (Summary, Transcript, etc.)
    doc_panels = panels.get(doc.get("id", ""), {})
    for panel_id, panel in doc_panels.items():
        title = panel.get("title", "")
        content = panel.get("content", "")

        if content:
            if isinstance(content, str):
                text = html_to_text(content)
            elif isinstance(content, dict):
                text = tiptap_to_text(content.get("content", []))
            else:
                text = ""

            if text.strip():
                parts.append(f"\n## {title}\n{text}")

    return "\n\n".join(parts)


def tiptap_to_text(content: Any) -> str:
    """Convert TipTap/ProseMirror content to plain text."""
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
                if item_type == 'paragraph':
                    parts.append(text + '\n')
                elif item_type == 'heading':
                    parts.append('\n' + text + '\n')
                elif item_type in ('bulletList', 'orderedList'):
                    parts.append(text)
                elif item_type == 'listItem':
                    parts.append('- ' + text + '\n')
                elif item_type == 'text':
                    parts.append(str(item.get('text', '')))
                else:
                    parts.append(text)
        return ''.join(parts)
    return str(content) if content else ''


def html_to_text(html: str) -> str:
    """Simple HTML to text conversion."""
    from html.parser import HTMLParser

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text_parts = []

        def handle_starttag(self, tag, attrs):
            if tag == 'li':
                self.text_parts.append('\n- ')
            elif tag in ('h1', 'h2', 'h3', 'p'):
                self.text_parts.append('\n')

        def handle_data(self, data):
            self.text_parts.append(data)

        def get_text(self):
            return ''.join(self.text_parts).strip()

    parser = TextExtractor()
    parser.feed(html)
    return parser.get_text()


def process_meeting_with_smart_paste(
    meeting_title: str,
    meeting_date: str,
    transcript: str,
    memory_bank: str,
    template: str
) -> Optional[str]:
    """Process a meeting transcript using Claude Sonnet with full SMART_PASTE context."""

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️  ANTHROPIC_API_KEY not set")
        return None

    client = anthropic.Anthropic(api_key=api_key)

    # Build the comprehensive prompt
    system_prompt = f"""You are a Product Manager's AI assistant processing meeting transcripts using the SMART_PASTE framework.

## Your Context - Badho Business
{memory_bank}

## Output Template Guidelines
{template[:1500]}

## Your Task
Process the meeting transcript and produce a structured meeting note with:
1. Executive Summary (TLDR, Key Decision, Business Impact)
2. Adaptive Themes with tagged insights: [decision], [action], [risk], [open-question], [insight]
3. ACTION ITEMS section with format: Owner: <name> | Task: <specific task> | Due: <date/relative> | Context: <theme>
4. DECISIONS section if any decisions were made

## Quality Standards
- Every section must provide genuine business value
- No placeholder text - extract REAL content
- Action items must have specific owners and timelines
- Connect insights to Badho's B2B marketplace context
- Be executive-ready and scannable
"""

    user_prompt = f"""Process this meeting transcript:

**Meeting Title:** {meeting_title}
**Date:** {meeting_date}

---

## TRANSCRIPT

{transcript[:12000]}

---

Generate a structured meeting note following the SMART_PASTE framework. Include all themes discussed, decisions made, and action items with clear ownership."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",  # Use Sonnet for quality
            max_tokens=4000,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
            system=system_prompt
        )

        return response.content[0].text

    except Exception as e:
        print(f"⚠️  Error processing with Claude: {e}")
        return None


def save_meeting_to_archive(
    meeting_id: str,
    meeting_title: str,
    meeting_date: datetime,
    processed_content: str
) -> Path:
    """Save processed meeting to the archive."""

    # Create year directory
    year_dir = MEETING_ARCHIVE_PATH / str(meeting_date.year)
    year_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    date_str = meeting_date.strftime("%Y-%m-%d")
    title_slug = re.sub(r'[^a-z0-9]+', '-', meeting_title.lower()).strip('-')[:50]
    filename = f"{date_str}_{title_slug}.md"
    filepath = year_dir / filename

    # Add metadata header
    full_content = f"""---
meeting_id: {meeting_id}
processed_at: {datetime.now().isoformat()}
source: granola_smart_paste
---

{processed_content}
"""

    filepath.write_text(full_content)
    return filepath


def update_meeting_index(filepath: Path, meeting_title: str, meeting_date: datetime):
    """Update the MEETING_INDEX.md file."""
    index_path = MEETING_ARCHIVE_PATH / "MEETING_INDEX.md"

    # Create index if it doesn't exist
    if not index_path.exists():
        index_path.write_text("# Meeting Index\n\nAutomatically updated by SMART_PASTE processor.\n\n## Meetings\n\n")

    # Read existing content
    content = index_path.read_text()

    # Add new entry
    relative_path = filepath.relative_to(MEETING_ARCHIVE_PATH)
    date_str = meeting_date.strftime("%Y-%m-%d")
    new_entry = f"- [{date_str}] [{meeting_title}]({relative_path})\n"

    # Insert after "## Meetings" header
    if "## Meetings" in content:
        parts = content.split("## Meetings\n\n")
        content = parts[0] + "## Meetings\n\n" + new_entry + (parts[1] if len(parts) > 1 else "")
    else:
        content += f"\n## Meetings\n\n{new_entry}"

    index_path.write_text(content)


def get_recent_meetings(hours: int = 24) -> List[Dict[str, Any]]:
    """Get meetings from the last N hours that haven't been processed."""
    state = load_granola_cache()
    if not state:
        return []

    documents = state.get("documents", {})
    panels = state.get("documentPanels", {})
    processed = get_processed_meetings()

    cutoff = datetime.now() - timedelta(hours=hours)
    meetings = []

    for doc_id, doc in documents.items():
        # Skip if already processed
        if doc_id in processed:
            continue

        # Skip deleted docs
        if doc.get("deleted_at"):
            continue

        # Check timestamp
        created_at = doc.get("created_at")
        if not created_at:
            continue

        try:
            doc_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            doc_time = doc_time.replace(tzinfo=None)

            if doc_time < cutoff:
                continue
        except:
            continue

        # Extract transcript
        transcript = extract_transcript_text(doc, panels)
        if len(transcript) < 200:  # Skip very short meetings
            continue

        meetings.append({
            "id": doc_id,
            "title": doc.get("title") or "Untitled Meeting",
            "created_at": doc_time,
            "transcript": transcript,
        })

    return meetings


def run_smart_paste_processor(hours: int = 24):
    """Main function to run the SMART_PASTE processor."""
    print("🧠 SMART_PASTE Processor")
    print("=" * 50)

    # Load context
    print("📚 Loading memory bank and templates...")
    memory_bank = load_memory_bank()
    template = load_smart_paste_template()

    if not memory_bank:
        print("⚠️  Warning: Memory bank is empty")

    # Get recent meetings
    print(f"📝 Scanning for meetings in last {hours} hours...")
    meetings = get_recent_meetings(hours)

    if not meetings:
        print("✅ No new meetings to process")
        return {"processed": 0, "meetings": []}

    print(f"   Found {len(meetings)} meetings to process")

    processed_meetings = []

    for meeting in meetings:
        print(f"\n🔄 Processing: {meeting['title']}")

        # Process with SMART_PASTE
        processed_content = process_meeting_with_smart_paste(
            meeting_title=meeting["title"],
            meeting_date=meeting["created_at"].strftime("%A, %B %d, %Y"),
            transcript=meeting["transcript"],
            memory_bank=memory_bank,
            template=template
        )

        if not processed_content:
            print(f"   ⚠️  Failed to process")
            continue

        # Save to archive
        filepath = save_meeting_to_archive(
            meeting_id=meeting["id"],
            meeting_title=meeting["title"],
            meeting_date=meeting["created_at"],
            processed_content=processed_content
        )
        print(f"   💾 Saved to: {filepath.name}")

        # Update index
        update_meeting_index(filepath, meeting["title"], meeting["created_at"])
        print(f"   📑 Updated MEETING_INDEX.md")

        # Mark as processed
        mark_meeting_processed(meeting["id"])

        processed_meetings.append({
            "id": meeting["id"],
            "title": meeting["title"],
            "filepath": str(filepath)
        })

    print(f"\n{'=' * 50}")
    print(f"✅ Processed {len(processed_meetings)} meetings")

    return {"processed": len(processed_meetings), "meetings": processed_meetings}


if __name__ == "__main__":
    import sys
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    run_smart_paste_processor(hours)
