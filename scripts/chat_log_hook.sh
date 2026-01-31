#!/usr/bin/env bash
# Hook: Export chat log on session end

# Read hook input from stdin
input=$(cat)

# Extract session info
session_id=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null)
cwd=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cwd',''))" 2>/dev/null)

if [[ -z "$session_id" ]]; then
    exit 0
fi

# Build JSONL path
project_encoded=$(echo "$cwd" | sed 's|/|-|g')
jsonl_path="$HOME/.claude/projects/${project_encoded}/${session_id}.jsonl"

if [[ -f "$jsonl_path" ]]; then
    /usr/bin/python3 /Users/mac/Projects/digiman/scripts/export_chat_log.py "$jsonl_path"
fi

exit 0
