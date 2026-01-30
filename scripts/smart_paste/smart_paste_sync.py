#!/usr/bin/env python3
"""
SMART_PASTE Sync - Resilient nightly processor using Claude Code CLI.

Features:
- Uses Claude Code CLI (not direct API) for full SMART_PASTE context
- State management for tracking processed meetings
- Multi-day backfill when laptop comes back online
- Dashboard integration for monitoring
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# Configuration
GRANOLA_CACHE_PATH = Path.home() / "Library/Application Support/Granola/cache-v3.json"
MYNOTES_PATH = Path.home() / "Downloads/MyNotes"
MEETING_ARCHIVE_PATH = MYNOTES_PATH / "02_Active_Projects/meeting_archive"
MEMORY_BANK_PATH = MYNOTES_PATH / "memory-bank"

# State files
DIGIMAN_DIR = Path.home() / ".digiman"
STATE_FILE = DIGIMAN_DIR / "sync_state.json"
STATUS_FILE = DIGIMAN_DIR / "cron_status.json"
LOG_DIR = DIGIMAN_DIR / "logs"

# Ensure directories exist
DIGIMAN_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log(message: str):
    """Log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


# ========== State Management ==========

def load_state() -> Dict[str, Any]:
    """Load sync state from file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except:
            pass
    return {
        "last_successful_sync": None,
        "processed_meeting_ids": [],
        "pending_backfill_days": 0
    }


def save_state(state: Dict[str, Any]):
    """Save sync state to file."""
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_processed_meeting_ids() -> set:
    """Get set of already processed meeting IDs."""
    state = load_state()
    return set(state.get("processed_meeting_ids", []))


def mark_meeting_processed(meeting_id: str):
    """Mark a meeting as processed in state."""
    state = load_state()
    processed = set(state.get("processed_meeting_ids", []))
    processed.add(meeting_id)
    # Keep only last 1000 IDs to prevent unbounded growth
    state["processed_meeting_ids"] = list(processed)[-1000:]
    save_state(state)


# ========== Dashboard Integration ==========

def update_dashboard_status(job_name: str, status: str, count: int = 0, message: str = None):
    """Update the cron_status.json for dashboard."""
    try:
        data = {}
        if STATUS_FILE.exists():
            try:
                data = json.loads(STATUS_FILE.read_text())
            except:
                pass

        # Ensure jobs dict exists
        if "jobs" not in data:
            data["jobs"] = {}

        now = datetime.now().isoformat()

        # Update the specific job
        data["jobs"][job_name] = {
            "name": get_job_display_name(job_name),
            "icon": get_job_icon(job_name),
            "description": get_job_description(job_name),
            "last_run": now,
            "last_status": status,
            "last_count": count,
            "last_message": message
        }

        # Update overall status if this is the main sync
        if job_name == "smart_paste":
            data["last_sync"] = now
            data["last_sync_status"] = status
            data["last_sync_count"] = count

            # Update sources
            sources = data.get("sources", [])
            if "SMART_PASTE" not in sources:
                sources.append("SMART_PASTE")
            data["sources"] = sources

        # Add to history
        if "history" not in data:
            data["history"] = []
        data["history"].insert(0, {
            "timestamp": now,
            "source": job_name,
            "status": status,
            "count": count,
            "error": message if status == "error" else None
        })
        data["history"] = data["history"][:50]  # Keep last 50

        # Update backfill status
        state = load_state()
        data["backfill"] = {
            "pending_days": state.get("pending_backfill_days", 0),
            "last_backfill": state.get("last_backfill"),
            "meetings_pending": len(get_unprocessed_meetings(hours=24 * state.get("pending_backfill_days", 0)))
        }

        # Update Claude Code status
        data["claude_code"] = {
            "available": check_claude_code_available(),
            "last_check": now
        }

        STATUS_FILE.write_text(json.dumps(data, indent=2))

    except Exception as e:
        log(f"Warning: Could not update dashboard status: {e}")


def get_job_display_name(job_name: str) -> str:
    """Get display name for job."""
    names = {
        "smart_paste": "SMART_PASTE",
        "watchdog": "Watchdog",
        "nightly_sync": "Nightly Sync",
        "morning_push": "Morning Push"
    }
    return names.get(job_name, job_name)


def get_job_icon(job_name: str) -> str:
    """Get icon for job."""
    icons = {
        "smart_paste": "🧠",
        "watchdog": "🐕",
        "nightly_sync": "📝",
        "morning_push": "🌅"
    }
    return icons.get(job_name, "⚙️")


def get_job_description(job_name: str) -> str:
    """Get description for job."""
    descriptions = {
        "smart_paste": "Process meetings via Claude Code",
        "watchdog": "Ensures sync completes",
        "nightly_sync": "Extract action items to Digiman",
        "morning_push": "Send todos to Slack"
    }
    return descriptions.get(job_name, "")


# ========== Claude Code Integration ==========

def check_claude_code_available() -> bool:
    """Check if Claude Code CLI is available and running."""
    try:
        result = subprocess.run(
            ["which", "claude"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False


def process_meeting_with_claude_code(
    meeting_title: str,
    meeting_date: str,
    transcript: str,
    output_path: Path
) -> bool:
    """Process a meeting using Claude Code CLI with full SMART_PASTE context."""

    # Create a temporary prompt file
    prompt_file = DIGIMAN_DIR / "temp_smart_paste_prompt.md"

    prompt_content = f"""Process this meeting transcript using the SMART_PASTE framework.

**Meeting Title:** {meeting_title}
**Date:** {meeting_date}

---

## TRANSCRIPT

{transcript[:15000]}

---

## Instructions

Generate a structured meeting note following the SMART_PASTE framework with:
1. Executive Summary (TLDR, Key Decision, Business Impact)
2. Adaptive Themes with tagged insights: [decision], [action], [risk], [open-question], [insight]
3. ACTION ITEMS section with format: Owner: <name> | Task: <specific task> | Due: <date/relative> | Context: <theme>
4. DECISIONS section if any decisions were made

Save the output to: {output_path}

Use the Badho business context from the memory-bank and CLAUDE.md files in the MyNotes workspace.
"""

    prompt_file.write_text(prompt_content)

    try:
        # Run Claude Code CLI with the prompt
        # Using --print to get output and --dangerously-skip-permissions to avoid prompts in cron
        result = subprocess.run(
            [
                "claude",
                "--print",
                "--dangerously-skip-permissions",
                "-p", prompt_content
            ],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=str(MYNOTES_PATH)  # Run in MyNotes directory for context
        )

        if result.returncode == 0:
            # Claude Code was successful - check if file was created
            if output_path.exists():
                log(f"   ✓ Claude Code processed and saved to {output_path.name}")
                return True
            else:
                # Claude might have output to stdout instead of saving
                if result.stdout.strip():
                    # Save the output manually
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                    # Add metadata header
                    full_content = f"""---
processed_at: {datetime.now().isoformat()}
source: claude_code_smart_paste
---

{result.stdout}
"""
                    output_path.write_text(full_content)
                    log(f"   ✓ Saved Claude Code output to {output_path.name}")
                    return True

        log(f"   ⚠️ Claude Code failed: {result.stderr[:200]}")
        return False

    except subprocess.TimeoutExpired:
        log("   ⚠️ Claude Code timed out")
        return False
    except Exception as e:
        log(f"   ⚠️ Error running Claude Code: {e}")
        return False
    finally:
        # Cleanup temp file
        if prompt_file.exists():
            prompt_file.unlink()


# ========== Granola Cache Processing ==========

def load_granola_cache() -> Dict[str, Any]:
    """Load and parse the Granola cache."""
    if not GRANOLA_CACHE_PATH.exists():
        log(f"⚠️  Granola cache not found at: {GRANOLA_CACHE_PATH}")
        return {}

    try:
        with open(GRANOLA_CACHE_PATH, "r", encoding="utf-8") as f:
            outer_data = json.load(f)

        cache_str = outer_data.get("cache", "{}")
        cache_data = json.loads(cache_str)
        return cache_data.get("state", {})
    except Exception as e:
        log(f"⚠️  Error parsing Granola cache: {e}")
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


def get_unprocessed_meetings(hours: int = 24) -> List[Dict[str, Any]]:
    """Get meetings from the last N hours that haven't been processed."""
    state = load_granola_cache()
    if not state:
        return []

    documents = state.get("documents", {})
    panels = state.get("documentPanels", {})
    processed = get_processed_meeting_ids()

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


# ========== Main Processing ==========

def calculate_backfill_days() -> int:
    """Calculate how many days of backfill are needed."""
    state = load_state()
    last_sync = state.get("last_successful_sync")

    if not last_sync:
        return 7  # First run - backfill 7 days

    try:
        last_sync_dt = datetime.fromisoformat(last_sync)
        days_since = (datetime.now() - last_sync_dt).days
        return min(days_since, 30)  # Cap at 30 days
    except:
        return 1


def run_smart_paste_sync(hours: int = None, backfill: bool = True) -> Dict[str, Any]:
    """Main function to run the SMART_PASTE sync."""
    log("🧠 SMART_PASTE Sync")
    log("=" * 50)

    # Update dashboard that we're starting
    update_dashboard_status("smart_paste", "running", message="Starting sync...")

    # Calculate hours to look back
    if hours is None:
        if backfill:
            backfill_days = calculate_backfill_days()
            hours = max(24, backfill_days * 24)
            log(f"📅 Backfill mode: looking back {backfill_days} days ({hours} hours)")
        else:
            hours = 24

    # Check Claude Code availability
    if not check_claude_code_available():
        log("⚠️  Claude Code CLI not available")
        update_dashboard_status("smart_paste", "error", message="Claude Code not available")
        return {"processed": 0, "error": "Claude Code not available"}

    log("✓ Claude Code CLI available")

    # Get unprocessed meetings
    log(f"📝 Scanning for meetings in last {hours} hours...")
    meetings = get_unprocessed_meetings(hours)

    if not meetings:
        log("✅ No new meetings to process")

        # Update state
        state = load_state()
        state["last_successful_sync"] = datetime.now().isoformat()
        state["pending_backfill_days"] = 0
        save_state(state)

        update_dashboard_status("smart_paste", "success", count=0, message="No new meetings")
        return {"processed": 0, "meetings": []}

    log(f"   Found {len(meetings)} meetings to process")

    processed_meetings = []
    errors = []

    for meeting in meetings:
        log(f"\n🔄 Processing: {meeting['title']}")

        # Generate output path
        year_dir = MEETING_ARCHIVE_PATH / str(meeting["created_at"].year)
        year_dir.mkdir(parents=True, exist_ok=True)

        date_str = meeting["created_at"].strftime("%Y-%m-%d")
        title_slug = re.sub(r'[^a-z0-9]+', '-', meeting["title"].lower()).strip('-')[:50]
        filename = f"{date_str}_{title_slug}.md"
        output_path = year_dir / filename

        # Process with Claude Code
        success = process_meeting_with_claude_code(
            meeting_title=meeting["title"],
            meeting_date=meeting["created_at"].strftime("%A, %B %d, %Y"),
            transcript=meeting["transcript"],
            output_path=output_path
        )

        if success:
            # Mark as processed
            mark_meeting_processed(meeting["id"])

            # Update meeting index
            update_meeting_index(output_path, meeting["title"], meeting["created_at"])
            log(f"   📑 Updated MEETING_INDEX.md")

            processed_meetings.append({
                "id": meeting["id"],
                "title": meeting["title"],
                "filepath": str(output_path)
            })
        else:
            errors.append(f"Failed to process: {meeting['title']}")

    # Update state
    state = load_state()
    state["last_successful_sync"] = datetime.now().isoformat()
    state["pending_backfill_days"] = 0
    if errors:
        state["last_errors"] = errors[:5]  # Keep last 5 errors
    save_state(state)

    # Summary
    log(f"\n{'=' * 50}")
    log(f"✅ Processed {len(processed_meetings)} meetings")
    if errors:
        log(f"⚠️  {len(errors)} errors occurred")

    # Update dashboard
    status = "success" if not errors else "partial"
    update_dashboard_status(
        "smart_paste",
        status,
        count=len(processed_meetings),
        message=errors[0] if errors else None
    )

    return {
        "processed": len(processed_meetings),
        "meetings": processed_meetings,
        "errors": errors
    }


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

    # Check if entry already exists
    if str(relative_path) in content:
        return

    # Insert after "## Meetings" header
    if "## Meetings" in content:
        parts = content.split("## Meetings\n\n")
        content = parts[0] + "## Meetings\n\n" + new_entry + (parts[1] if len(parts) > 1 else "")
    else:
        content += f"\n## Meetings\n\n{new_entry}"

    index_path.write_text(content)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SMART_PASTE Sync with Claude Code")
    parser.add_argument("--hours", type=int, help="Hours to look back (default: auto-calculate)")
    parser.add_argument("--no-backfill", action="store_true", help="Disable backfill mode")

    args = parser.parse_args()

    result = run_smart_paste_sync(hours=args.hours, backfill=not args.no_backfill)

    # Exit with error code if there were failures
    if result.get("errors"):
        sys.exit(1)
