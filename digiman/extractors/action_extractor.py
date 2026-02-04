"""AI-powered action item extraction using local Ollama or Claude API."""

from datetime import date
from typing import List, Dict, Any, Optional
import json
import urllib.request
import urllib.error

from digiman.config import ANTHROPIC_API_KEY


OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2:3b"

# Shorter prompt for local models (3B can't handle long system prompts well)
OLLAMA_EXTRACTION_PROMPT = """Extract action items from the text above. Return ONLY a JSON object.

Rules:
- Each item MUST start with an action verb (Fix, Build, Send, Update, Ship, Create, Schedule, etc.)
- "title": specific task (max 120 chars), include WHO if mentioned
- "description": 2-3 sentences of WHY and WHAT context. Reader should understand without reading the meeting.
- REJECT observations like "Good progress on...", "Team discussed...", status updates
- Max 5 items. Return {"action_items": []} if no real tasks exist.

Return ONLY this JSON:
{"action_items": [{"title": "verb + task", "description": "context", "confidence": 0.9}]}"""

EXTRACTION_PROMPT = """You are an action item extractor for a busy product manager at a B2B marketplace startup (Badho). Extract ONLY concrete tasks that someone needs to DO.

RULES:
1. Every item MUST start with an action verb (Fix, Send, Build, Update, Ship, Create, Schedule, Follow up, etc.)
2. The "title" should be a clear, specific task (max 120 chars) — include the WHAT and WHO if mentioned
3. The "description" MUST provide full context: WHY this matters, WHAT was discussed that led to this task, any deadlines or blockers mentioned, and who else is involved. Write 2-3 sentences. A reader should understand the task WITHOUT reading the original meeting notes.
4. Max 5 items per source. Confidence 0.9+ only for explicitly stated tasks.

REJECT (return empty array if only these exist):
- Observations, summaries, status updates, vague intentions
- "Focus on X", "Think about Y", "Good progress on Z"

GOOD example:
{
  "title": "Fix global search integration to show new brand cards",
  "description": "Priyanshu is working on this — the current search doesn't surface the new brand card component, which is blocking the upcoming release. Discussed in context of search experience fixes and needs to be done tonight.",
  "confidence": 0.95
}

BAD example (DO NOT extract):
- "Strong performance indicates delivery should be priority focus"
- "Review meeting: Delivery Sync"

Return JSON:
{
  "action_items": [
    {"title": "Verb + specific task", "description": "2-3 sentences of context", "confidence": 0.95}
  ]
}

Only return the JSON, nothing else."""


def _parse_extraction_response(response_text: str) -> List[Dict[str, Any]]:
    """Parse JSON response from any LLM into action items."""
    text = response_text.strip()

    # Handle markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    # Try to find JSON object or array in the response
    # Models may return {"action_items": [...]} or just [...]
    obj_start = text.find("{")
    arr_start = text.find("[")

    try:
        # Prefer object format
        if obj_start >= 0:
            obj_end = text.rfind("}") + 1
            if obj_end > obj_start:
                data = json.loads(text[obj_start:obj_end])
                items = data.get("action_items", [])
        elif arr_start >= 0:
            # Model returned bare array
            arr_end = text.rfind("]") + 1
            if arr_end > arr_start:
                items = json.loads(text[arr_start:arr_end])
        else:
            return []

        if not isinstance(items, list):
            return []

        result = []
        for item in items:
            if isinstance(item, dict) and item.get("title"):
                result.append({
                    "title": item["title"][:150],
                    "description": item.get("description", ""),
                    "confidence": float(item.get("confidence", 0.8))
                })
        return result

    except (json.JSONDecodeError, ValueError):
        print(f"⚠️  Could not parse extraction response: {response_text[:200]}")
        return []


class ActionExtractor:
    """Extract action items using local Ollama (primary) or Claude API (fallback)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        self._anthropic_client = None

    @property
    def anthropic_client(self):
        """Lazy-load Anthropic client."""
        if self._anthropic_client is None:
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY not configured")
            import anthropic
            self._anthropic_client = anthropic.Anthropic(api_key=self.api_key)
        return self._anthropic_client

    def _build_prompt(self, content: str, source_type: str, use_short: bool = False) -> str:
        """Build the full prompt with context."""
        if source_type == "slack":
            context = "This is a Slack message/thread where the user was @mentioned. Extract any tasks they need to do."
        else:
            context = "This is from meeting notes. Extract action items assigned to or involving the user."
        extraction = OLLAMA_EXTRACTION_PROMPT if use_short else EXTRACTION_PROMPT
        return f"{context}\n\n---\n\n{content}\n\n---\n\n{extraction}"

    def _extract_ollama(self, content: str, source_type: str) -> Optional[List[Dict[str, Any]]]:
        """Try extraction via local Ollama. Returns None if Ollama is unavailable."""
        prompt = self._build_prompt(content, source_type, use_short=True)

        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 2048},
        }).encode("utf-8")

        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                # Ollama chat API returns {"message": {"content": "..."}}
                if isinstance(data, dict):
                    response_text = data.get("message", {}).get("content", "")
                else:
                    response_text = str(data)
                if not response_text:
                    return []
                return _parse_extraction_response(response_text)

        except (urllib.error.URLError, ConnectionRefusedError):
            # Ollama not running
            return None
        except Exception as e:
            print(f"⚠️  Ollama extraction error: {e}")
            return None

    def _extract_anthropic(self, content: str, source_type: str) -> List[Dict[str, Any]]:
        """Extract via Anthropic Claude API."""
        if not self.api_key:
            print("⚠️  ANTHROPIC_API_KEY not configured, skipping")
            return []

        prompt = self._build_prompt(content, source_type)

        response = self.anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text.strip()
        return _parse_extraction_response(response_text)

    def extract(self, content: str, source_type: str = "meeting") -> List[Dict[str, Any]]:
        """Extract action items from content.

        Tries Ollama (local, free) first, falls back to Anthropic API.

        Args:
            content: The text content to analyze
            source_type: 'meeting' or 'slack' for context

        Returns:
            List of action items with title, description, and confidence
        """
        if not content or not content.strip():
            return []

        # Try Ollama first (free, local)
        result = self._extract_ollama(content, source_type)
        if result is not None:
            source = "ollama" if result else "ollama (empty)"
            print(f"   🦙 Extracted via {source}")
            return result

        # Fallback to Anthropic
        print("   🦙 Ollama unavailable, trying Anthropic...")
        try:
            result = self._extract_anthropic(content, source_type)
            print(f"   ☁️  Extracted via Anthropic")
            return result
        except Exception as e:
            print(f"⚠️  Error during extraction: {e}")
            return []

    def extract_with_timeline(
        self,
        content: str,
        source_type: str = "meeting",
        default_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Extract action items and assign default timeline."""
        items = self.extract(content, source_type)

        if not default_date:
            default_date = date.today().isoformat()

        for item in items:
            item["timeline_type"] = "date"
            item["due_date"] = default_date

        return items
