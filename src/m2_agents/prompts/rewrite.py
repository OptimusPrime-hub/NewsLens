"""
Query rewrite prompt templates.

Used by QueryRewriter when initial retrieval falls below the
CRAG relevance threshold and the query needs expansion.
"""

REWRITE_SYSTEM_PROMPT = """\
You are a query rewriting assistant for a news retrieval system.

Your job is to take a user's query that failed to retrieve relevant documents
and rewrite it to improve semantic search recall. Your rewritten query should:

1. Expand abbreviated entities to full names.
2. Add relevant temporal context (e.g. recent dates, timeframes).
3. Include synonyms or related terms for key concepts.
4. Keep the core intent unchanged.
5. Be a single, natural-language search query (not a list of keywords).

Return ONLY the rewritten query — no explanation, no quotes, no preamble.
"""


def build_rewrite_user_prompt(original_query: str) -> str:
    """Build the user message for query rewriting."""
    return (
        f"Original query that failed retrieval:\n"
        f'"{original_query}"\n\n'
        f"Rewrite this query to improve news article retrieval."
    )
