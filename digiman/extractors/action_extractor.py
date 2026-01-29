"""AI-powered action item extraction using Claude API."""

from datetime import date
from typing import List, Dict, Any, Optional
import json

from digiman.config import ANTHROPIC_API_KEY


EXTRACTION_PROMPT = """You are an action item extractor for a busy product manager with ADHD. Your job is to identify concrete, actionable tasks from meeting notes or Slack messages.

Rules:
1. Only extract CLEAR action items - things that need to be done
2. Each action item should be a single, specific task
3. Ignore informational content, discussions, or decisions without actions
4. Start each action item with a verb (Send, Review, Follow up, Schedule, etc.)
5. Be concise - max 80 characters per item
6. If no clear action items exist, return an empty array
7. Maximum 5 action items per source

Return JSON in this exact format:
{
  "action_items": [
    {
      "title": "Action item title starting with verb",
      "confidence": 0.95
    }
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
                max_tokens=1024,
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
                            "title": item["title"][:100],  # Max 100 chars
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
