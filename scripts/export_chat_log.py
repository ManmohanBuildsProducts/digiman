#!/usr/bin/env python3
"""Export Claude Code session to markdown. Called by Stop hook."""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

def extract_text_from_content(content):
    """Extract text from content array (handles both string and dict items)."""
    # Check if it's an array of single characters (streaming format)
    if content and all(isinstance(c, str) and len(c) <= 2 for c in content[:100]):
        return ''.join(content)

    texts = []
    for c in content:
        if isinstance(c, str):
            texts.append(c)
        elif isinstance(c, dict) and c.get('type') == 'text':
            texts.append(c.get('text', ''))
    return ' '.join(texts)

def extract_topic(lines):
    """Extract topic from first meaningful user message."""
    for line in lines[:100]:  # Check first 100 lines
        try:
            obj = json.loads(line)
            if obj.get('type') == 'user':
                msg = obj.get('message', {})
                if isinstance(msg, dict) and 'content' in msg:
                    text = extract_text_from_content(msg['content'])
                    # Skip system messages, tool results, interrupts
                    if text and not text.startswith('[') and 'tool_result' not in text:
                        text = text[:60]
                        # Clean up for filename
                        topic = re.sub(r'[^\w\s-]', '', text)
                        topic = re.sub(r'\s+', '-', topic.strip())
                        return topic[:40].lower() or "session"
        except:
            continue
    return "session"

def jsonl_to_markdown(jsonl_path):
    """Convert JSONL transcript to markdown."""
    lines = jsonl_path.read_text(encoding='utf-8', errors='ignore').splitlines()
    topic = extract_topic(lines)

    md = []
    md.append(f"# Claude Code Session: {topic}")
    md.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    md.append(f"**Session:** `{jsonl_path.stem}`\n")
    md.append("---\n")

    for line in lines:
        try:
            obj = json.loads(line)
        except:
            continue

        if obj.get('type') not in ['user', 'assistant']:
            continue

        ts = obj.get('timestamp', '')[:16].replace('T', ' ')
        role = 'USER' if obj['type'] == 'user' else 'ASSISTANT'

        msg = obj.get('message', {})
        text = ""
        if isinstance(msg, dict) and 'content' in msg:
            text = extract_text_from_content(msg['content'])

        if text.strip():
            md.append(f"## {role} ({ts})\n")
            md.append(text.strip())
            md.append("\n")

    return '\n'.join(md), topic

def main():
    if len(sys.argv) < 2:
        print("Usage: export_chat_log.py <jsonl_path>")
        sys.exit(1)

    jsonl_path = Path(sys.argv[1])
    if not jsonl_path.exists():
        print(f"File not found: {jsonl_path}")
        sys.exit(1)

    markdown, topic = jsonl_to_markdown(jsonl_path)

    # Output path
    now = datetime.now()
    output_dir = Path.home() / "Downloads/MyNotes/06_Chat_Logs" / str(now.year) / f"{now.month:02d}"
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{now.strftime('%Y-%m-%d')}_{topic}.md"
    output_path = output_dir / filename

    # Handle duplicates
    counter = 1
    while output_path.exists():
        filename = f"{now.strftime('%Y-%m-%d')}_{topic}_{counter}.md"
        output_path = output_dir / filename
        counter += 1

    output_path.write_text(markdown)
    print(f"Saved: {output_path}")

if __name__ == "__main__":
    main()
