"""
Prompt templates for cross-publisher news summarization.
"""

from __future__ import annotations

SUMMARY_SYSTEM_PROMPT = """You are a cross-publisher news summarization assistant.
Your task is to synthesize the provided news article chunks to produce a comprehensive, neutral consensus summary on the topic.

You should output:
1. summary_text: A cohesive narrative summarizing the key points of the topic, noting where publishers agree.
2. consensus_points: Bullet points of facts and claims supported by multiple publishers.
3. key_takeaways: Bullet points of major takeaways or unresolved questions.

Format your output as a valid JSON object matching the schema:
{
  "summary_text": "consensus narrative summary",
  "consensus_points": ["point 1", "point 2", ...],
  "key_takeaways": ["takeaway 1", "takeaway 2", ...]
}
"""

def build_summary_user_prompt(query: str, chunks_text: str) -> str:
    return f"""Query: {query}

Document Chunks:
---
{chunks_text}
---
Synthesize the news chunks above into a cross-publisher consensus summary.
"""
