#!/usr/bin/env python3
"""Nightly sync script - Run at 11 PM via cron/launchd."""

import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from datetime import date, datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Status file for menu bar app
STATUS_FILE = Path.home() / ".digiman" / "cron_status.json"

from digiman.models import Todo, SyncHistory, init_db
from digiman.ingesters import GranolaIngester, SlackIngester
from digiman.ingesters.meeting_archive import MeetingArchiveIngester
from digiman.extractors import ActionExtractor


def clean_text(text: str) -> str:
    """Clean text - remove newlines but preserve full content."""
    return text.strip().replace("\n", " ").replace("  ", " ")


def run_sync(hours: int = 24) -> dict:
    """Run the full sync process.

    Uses Granola's built-in action items (no AI extraction).
    Captures Slack @mentions as todos directly.

    Args:
        hours: Look back this many hours for new content

    Returns:
        Dict with sync statistics
    """
    print("🧠 Digiman Nightly Sync")
    print("=" * 40)

    # Ensure database exists
    init_db()

    # Track stats
    stats = {
        "granola_processed": 0,
        "granola_extracted": 0,
        "meeting_archive_processed": 0,
        "meeting_archive_extracted": 0,
        "slack_processed": 0,
        "slack_extracted": 0,
        "errors": []
    }

    # Start sync record
    sync_id = SyncHistory.start("full")

    # Initialize ingesters and extractors
    granola = GranolaIngester()
    slack = SlackIngester()
    extractor = ActionExtractor()

    today = date.today().isoformat()

    # ========== Granola Sync ==========
    print("\n📝 Processing Granola meetings...")
    try:
        meetings = granola.get_recent_meetings(hours=hours)
        print(f"   Found {len(meetings)} new meetings")

        for meeting in meetings:
            try:
                # Use action items extracted from summary
                action_items = meeting.get("action_items", [])

                if action_items:
                    # Create SUGGESTIONS from extracted action items
                    for item in action_items:
                        title = clean_text(str(item))
                        if not title:
                            continue

                        suggestion = Todo(
                            title=title,
                            source_type="granola",
                            source_id=meeting["id"],
                            source_context=meeting["title"],
                            source_url=meeting.get("url"),
                            is_suggestion=True,  # Mark as suggestion, not todo
                        )
                        suggestion.save()
                        stats["granola_extracted"] += 1

                    print(f"   ✓ {meeting['title']}: {len(action_items)} suggestions")
                else:
                    # No regex matches - try AI extraction as fallback
                    ai_items = []
                    try:
                        content = granola.get_content_for_extraction(meeting)
                        if content.strip():
                            ai_items = extractor.extract(content, source_type="meeting")
                    except Exception as e:
                        print(f"   ⚠️  AI extraction failed: {e}")

                    if ai_items:
                        for ai_item in ai_items:
                            title = clean_text(ai_item.get("title", ""))
                            if not title:
                                continue
                            suggestion = Todo(
                                title=title,
                                source_type="granola",
                                source_id=meeting["id"],
                                source_context=meeting["title"],
                                source_url=meeting.get("url"),
                                is_suggestion=True,
                                extraction_confidence=ai_item.get("confidence", 0.8),
                            )
                            suggestion.save()
                            stats["granola_extracted"] += 1
                        print(f"   ✓ {meeting['title']}: {len(ai_items)} suggestions (AI)")
                    else:
                        # Neither regex nor AI found anything
                        meeting_title = clean_text(meeting["title"])
                        suggestion = Todo(
                            title=f"Review meeting: {meeting_title}",
                            source_type="granola",
                            source_id=meeting["id"],
                            source_context=meeting["title"],
                            source_url=meeting.get("url"),
                            is_suggestion=True,
                        )
                        suggestion.save()
                        stats["granola_extracted"] += 1
                        print(f"   ○ {meeting['title']}: created review suggestion")

                # Mark as processed
                granola.mark_processed(meeting["id"])
                stats["granola_processed"] += 1

            except Exception as e:
                error = f"Error processing meeting {meeting.get('id')}: {e}"
                print(f"   ❌ {error}")
                stats["errors"].append(error)

    except Exception as e:
        error = f"Granola sync error: {e}"
        print(f"   ❌ {error}")
        stats["errors"].append(error)

    # ========== Meeting Archive Sync (SMART_PASTE processed files) ==========
    print("\n📂 Processing SMART_PASTE meeting archive...")
    try:
        archive = MeetingArchiveIngester()
        processed_meetings = archive.get_recent_meetings(hours=hours)
        print(f"   Found {len(processed_meetings)} processed meetings")

        for meeting in processed_meetings:
            try:
                action_items = meeting.get("action_items", [])

                for item in action_items:
                    title = item.get("title", "")
                    if not title:
                        continue

                    # Include owner in title if available
                    owner = item.get("owner")
                    if owner:
                        title = f"{title} (Owner: {owner})"

                    suggestion = Todo(
                        title=clean_text(title),
                        description=f"Due: {item.get('due', 'TBD')} | Context: {item.get('context', 'N/A')}",
                        source_type="granola",  # Keep as granola for consistency
                        source_id=meeting["id"],
                        source_context=meeting["title"],
                        is_suggestion=True,
                        extraction_confidence=item.get("confidence", 0.9)
                    )
                    suggestion.save()
                    stats["meeting_archive_extracted"] += 1

                print(f"   ✓ {meeting['title']}: {len(action_items)} structured action items")

                archive.mark_processed(meeting["id"])
                stats["meeting_archive_processed"] += 1

            except Exception as e:
                error = f"Error processing archive meeting {meeting.get('id')}: {e}"
                print(f"   ❌ {error}")
                stats["errors"].append(error)

    except Exception as e:
        error = f"Meeting archive sync error: {e}"
        print(f"   ❌ {error}")
        stats["errors"].append(error)

    # ========== Slack Sync ==========
    print("\n💬 Processing Slack mentions...")
    try:
        mentions = slack.get_recent_mentions(hours=hours)
        print(f"   Found {len(mentions)} new mentions")
        print("   📝 Using regex-based extraction (no API needed)")

        for mention in mentions:
            try:
                channel_name = mention.get('channel_name', 'unknown')
                is_thread = bool(mention.get("thread_ts"))
                context_type = "thread" if is_thread else "channel"

                # Get full context (thread or surrounding messages)
                full_context = slack.get_full_context(mention)

                if not full_context.strip():
                    continue

                # Extract action items using regex patterns (like Granola)
                action_items = slack.extract_action_items(full_context)

                if action_items:
                    # Create suggestions from extracted action items
                    for item in action_items:
                        item_clean = clean_text(item)
                        if not item_clean or len(item_clean) < 5:
                            continue

                        # Title: concise (80 chars max, word boundary)
                        title = item_clean[:80].rsplit(' ', 1)[0] if len(item_clean) > 80 else item_clean
                        # Description: full text if truncated
                        description = item_clean if len(item_clean) > 80 else None

                        suggestion = Todo(
                            title=title,
                            description=description,
                            source_type="slack",
                            source_id=mention["id"],
                            source_context=f"#{channel_name}",
                            source_url=mention.get("permalink"),
                            is_suggestion=True,
                        )
                        suggestion.save()
                        stats["slack_extracted"] += 1

                    print(f"   ✓ #{channel_name} ({context_type}): {len(action_items)} action items extracted")
                else:
                    # No action items found - create a review suggestion with full context
                    text = mention.get("text", "")
                    import re
                    # Remove user mentions for clean title
                    cleaned = re.sub(r'<@[A-Z0-9]+>', '', text)
                    cleaned = clean_text(cleaned)

                    username = mention.get("username", "")
                    # Title: concise summary (first 80 chars, no "...")
                    title_text = cleaned[:80].rsplit(' ', 1)[0] if len(cleaned) > 80 else cleaned
                    title = f"@{username}: {title_text}" if username else title_text

                    # Description: full message for context
                    description = cleaned if len(cleaned) > 80 else None

                    suggestion = Todo(
                        title=title,
                        description=description,
                        source_type="slack",
                        source_id=mention["id"],
                        source_context=f"#{channel_name}",
                        source_url=mention.get("permalink"),
                        is_suggestion=True,
                    )
                    suggestion.save()
                    stats["slack_extracted"] += 1
                    print(f"   ○ #{channel_name} ({context_type}): no actions found, created review suggestion")

                # Mark as processed
                slack.mark_processed(mention["id"])
                stats["slack_processed"] += 1

            except Exception as e:
                error = f"Error processing mention {mention.get('id')}: {e}"
                print(f"   ❌ {error}")
                stats["errors"].append(error)

    except Exception as e:
        error = f"Slack sync error: {e}"
        print(f"   ❌ {error}")
        stats["errors"].append(error)

    # Complete sync record
    total_processed = stats["granola_processed"] + stats["meeting_archive_processed"] + stats["slack_processed"]
    total_extracted = stats["granola_extracted"] + stats["meeting_archive_extracted"] + stats["slack_extracted"]
    errors_str = "; ".join(stats["errors"]) if stats["errors"] else None

    SyncHistory.complete(sync_id, total_processed, total_extracted, errors_str)

    # Summary
    print("\n" + "=" * 40)
    print("📊 Sync Summary:")
    print(f"   Granola (raw): {stats['granola_processed']} meetings → {stats['granola_extracted']} todos")
    print(f"   Meeting Archive (SMART_PASTE): {stats['meeting_archive_processed']} meetings → {stats['meeting_archive_extracted']} todos")
    print(f"   Slack: {stats['slack_processed']} mentions → {stats['slack_extracted']} todos")
    if stats["errors"]:
        print(f"   Errors: {len(stats['errors'])}")
    print("✅ Sync complete!")

    # Update status file for menu bar app
    update_status_file(stats, total_extracted)

    # Push to cloud (non-fatal)
    try:
        push_to_cloud()
    except Exception as e:
        print(f"   ⚠️  Cloud push error (non-fatal): {e}")

    return {
        "new_todos": total_extracted,
        "processed": total_processed,
        "errors": stats["errors"]
    }


def push_to_cloud():
    """Push pending suggestions to PythonAnywhere (whileyousleep.xyz).

    Non-fatal: errors are logged but don't affect the sync.
    Server-side deduplication means we can safely send all pending suggestions.
    """
    print("\n☁️  Pushing suggestions to cloud...")

    config_path = Path(__file__).parent.parent / ".pythonanywhere-config.json"
    if not config_path.exists():
        print("   ⚠️  .pythonanywhere-config.json not found, skipping cloud sync")
        return

    try:
        config = json.loads(config_path.read_text())
        app_url = config.get("app_url", "").rstrip("/")
        deploy_secret = config.get("deploy_secret", "")

        if not app_url or not deploy_secret:
            print("   ⚠️  Missing app_url or deploy_secret in config, skipping")
            return

        suggestions = Todo.get_suggestions()
        if not suggestions:
            print("   No pending suggestions to push")
            return

        payload = json.dumps({
            "suggestions": [s.to_dict() for s in suggestions]
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{app_url}/api/suggestions/import",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Deploy-Token": deploy_secret,
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        imported = result.get("imported", 0)
        skipped = result.get("skipped", 0)
        rejected = result.get("rejected", 0)
        print(f"   ✅ Cloud sync: {imported} imported, {skipped} skipped, {rejected} rejected")

    except urllib.error.URLError as e:
        print(f"   ❌ Cloud sync failed (network): {e}")
    except Exception as e:
        print(f"   ❌ Cloud sync failed: {e}")


def update_status_file(stats, total_extracted):
    """Update the status file for the menu bar app."""
    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Load existing status
        status = {}
        if STATUS_FILE.exists():
            try:
                status = json.loads(STATUS_FILE.read_text())
            except:
                pass

        # Update status
        now = datetime.now().isoformat()
        status["last_sync"] = now
        status["last_sync_status"] = "success" if not stats["errors"] else "error"
        status["last_sync_count"] = total_extracted

        # Determine active sources
        sources = []
        if stats["granola_processed"] > 0:
            sources.append("Granola")
        if stats["slack_processed"] > 0:
            sources.append("Slack")
        status["sources"] = sources

        # Add to history
        history = status.get("history", [])
        history.insert(0, {
            "timestamp": now,
            "status": "success" if not stats["errors"] else "error",
            "count": total_extracted,
            "source": "nightly_sync",
            "error": stats["errors"][0] if stats["errors"] else None
        })
        status["history"] = history[:50]  # Keep last 50 entries

        # Check integrations
        from digiman.config import SLACK_BOT_TOKEN, GRANOLA_CACHE_PATH
        status["granola_enabled"] = Path(GRANOLA_CACHE_PATH).exists() if GRANOLA_CACHE_PATH else False
        status["slack_enabled"] = bool(SLACK_BOT_TOKEN)
        status["morning_push_enabled"] = bool(SLACK_BOT_TOKEN)

        # Write status
        STATUS_FILE.write_text(json.dumps(status, indent=2))

    except Exception as e:
        print(f"Warning: Could not update status file: {e}")


if __name__ == "__main__":
    run_sync()
