#!/bin/bash
# Usage: ./scripts/debug-if-down.sh

cd "$(dirname "$0")/.." || exit 1

STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "https://www.whileyousleep.xyz")

if [ "$STATUS" = "200" ]; then
    echo "✅ Site is UP"
else
    echo "🚨 DOWN (status: $STATUS) - Invoking Claude..."
    claude "Digiman site is down (HTTP $STATUS). Check PythonAnywhere logs, recent commits, and fix the issue."
fi
