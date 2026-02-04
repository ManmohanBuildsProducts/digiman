"""AI-powered action item extraction using Claude API."""

from datetime import date
from typing import List, Dict, Any, Optional
import json

from digiman.config import ANTHROPIC_API_KEY


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


class ActionExtractor:
    """Extract action items from text using Claude API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        self._client = None

    @property
    def client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY not configured")
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def extract(self, content: str, source_type: str = "meeting") -> List[Dict[str, Any]]:
        """Extract action items from content.

        Args:
            content: The text content to analyze
            source_type: 'meeting' or 'slack' for context

        Returns:
            List of action items with title and confidence
        """
        if not content or not content.strip():
            return []

        if not self.api_key:
            print("⚠️  ANTHROPIC_API_KEY not configured, skipping extraction")
            return []

        try:
            # Add context about source type
            if source_type == "slack":
                context = "This is a Slack message/thread where the user was @mentioned. Extract any tasks they need to do."
            else:
                context = "This is from meeting notes. Extract action items assigned to or involving the user."

            response = self.client.messages.create(
                model="claude-3-haiku-20240307",  # Fast and cheap for extraction
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": f"{context}\n\n---\n\n{content}\n\n---\n\n{EXTRACTION_PROMPT}"
                    }
                ]
            )

            # Parse response
            response_text = response.content[0].text.strip()

            # Try to parse JSON
            try:
                # Handle potential markdown code blocks
                if response_text.startswith("```"):
                    lines = response_text.split("\n")
                    response_text = "\n".join(lines[1:-1])

                data = json.loads(response_text)
                items = data.get("action_items", [])

                # Validate and normalize
                result = []
                for item in items:
                    if isinstance(item, dict) and item.get("title"):
                        result.append({
                            "title": item["title"][:150],
                            "description": item.get("description", ""),
                            "confidence": float(item.get("confidence", 0.8))
                        })

                return result

            except json.JSONDecodeError:
                print(f"⚠️  Could not parse extraction response: {response_text[:200]}")
                return []

        except Exception as e:
            print(f"⚠️  Error during extraction: {e}")
            return []

    def extract_with_timeline(
        self,
        content: str,
        source_type: str = "meeting",
        default_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Extract action items and assign default timeline.

        Returns action items with timeline_type and due_date.
        """
        items = self.extract(content, source_type)

        if not default_date:
            default_date = date.today().isoformat()

        # Add timeline info to each item
        for item in items:
            item["timeline_type"] = "date"
            item["due_date"] = default_date

        return items
