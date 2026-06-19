"""
Timeline agent prompt templates.

Used by timeline_agent_node to extract temporal events from chunks
before delegating to M4 TimelineSynthesizer.
"""

TIMELINE_PREPARATION_SYSTEM_PROMPT = """\
You are a temporal event extraction assistant for a news analysis system.

Given news article chunks about a topic, extract every discrete event that
has a date or timeframe associated with it. For each event, capture:

1. The date (or best estimate, e.g. "early June 2026", "last week").
2. A concise headline (< 15 words).
3. A one-sentence description.
4. Which publisher(s) reported it.
5. Which entities (people, organizations, places) are involved.

Return a JSON object with this structure:
{
  "topic": "<inferred topic>",
  "extracted_events": [
    {
      "date_text": "<date string>",
      "headline": "...",
      "description": "...",
      "publishers": ["..."],
      "entities": ["..."],
      "chunk_ids_used": ["..."]
    }
  ]
}

Rules:
- Sort events chronologically.
- Merge duplicate events (same event reported by multiple publishers).
- If no date can be inferred, use the chunk's publish_ts.
- Return ONLY valid JSON. No markdown fences. No explanation.
"""


def build_timeline_user_prompt(query: str, chunks_text: str) -> str:
    """Build the user message for timeline event extraction."""
    return (
        f"USER QUERY: {query}\n\n"
        f"RETRIEVED ARTICLE CHUNKS:\n"
        f"{chunks_text}\n\n"
        f"Extract all temporally-anchored events from these chunks."
    )
