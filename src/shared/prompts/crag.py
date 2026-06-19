"""
CRAG evaluation prompt templates.
"""

from __future__ import annotations

CRAG_SYSTEM_PROMPT = """You are a relevance grading assistant for a news analysis system.

Your job is to evaluate whether a retrieved document chunk is relevant
to the user's query. You must classify each chunk into exactly ONE of
three grades:

- RELEVANT: The chunk directly answers or provides key information for the query.
- AMBIGUOUS: The chunk is tangentially related but doesn't directly address the query.
- IRRELEVANT: The chunk has no meaningful connection to the query.

Respond in EXACTLY this format (two lines, nothing else):
GRADE: <RELEVANT|AMBIGUOUS|IRRELEVANT>
REASON: <one-sentence justification>
"""

def build_crag_user_prompt(query: str, publisher: str, publish_date_str: str, chunk_text: str) -> str:
    """Build the user message for a single chunk evaluation."""
    return (
        f"USER QUERY: {query}\n\n"
        f"DOCUMENT CHUNK (publisher: {publisher}, date: {publish_date_str}):\n"
        f'"""\n{chunk_text}\n"""\n\n'
        "Grade this chunk's relevance to the query."
    )
