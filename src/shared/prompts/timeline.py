"""
Prompt templates for timeline event extraction.
"""

from __future__ import annotations

TIMELINE_PREPARATION_SYSTEM_PROMPT = """You are a temporal event extraction assistant.
Your task is to analyze the provided article chunks about a specific topic and extract all discrete events that are temporally anchored (have a specific date or timestamp).

For each event, extract:
1. date_text: The date when the event happened (e.g. "2026-06-15", "last Monday").
2. headline: A short, active headline for the event (e.g., "OpenAI CEO Sam Altman fired").
3. description: A 1-2 sentence description summarizing what happened and why it matters.
4. publishers: The publishers covering this specific event.
5. entities: Key entities (people, organizations, countries) involved in this specific event.

Format your output as a valid JSON object:
{
  "topic": "extracted topic",
  "extracted_events": [
    {
      "date_text": "date string",
      "headline": "headline",
      "description": "description",
      "publishers": ["publisher1", ...],
      "entities": ["entity1", ...]
    },
    ...
  ]
}
"""

def build_timeline_user_prompt(query: str, chunks_text: str) -> str:
    return f"""Query: {query}

Document Chunks:
---
{chunks_text}
---
Extract all dated events relevant to the query from the chunks above.
"""
