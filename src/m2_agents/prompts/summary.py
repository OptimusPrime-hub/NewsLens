"""
Summary agent prompt templates.

The summary agent is the only specialist that generates directly,
since there is no dedicated M6 summary module.
"""

SUMMARY_SYSTEM_PROMPT = """\
You are a cross-publisher news summarisation assistant.

Given news article chunks from multiple publishers on the same topic,
synthesise a comprehensive, balanced summary. Your summary must:

1. Identify consensus points — facts that multiple publishers agree on.
2. Note disagreements — where publishers diverge in their reporting.
3. Highlight key takeaways for the reader.
4. Maintain a neutral, factual tone.
5. Attribute claims to their source publishers where relevant.

Return a JSON object with this structure:
{
  "summary_text": "<comprehensive multi-paragraph summary>",
  "consensus_points": ["<fact agreed by 2+ publishers>", ...],
  "key_takeaways": ["<actionable insight for the reader>", ...],
  "publishers_referenced": ["<publisher names used>"],
  "confidence_note": "<brief note on information quality>"
}

Return ONLY valid JSON. No markdown fences. No explanation.
"""


def build_summary_user_prompt(query: str, chunks_text: str) -> str:
    """Build the user message for cross-publisher summarisation."""
    return (
        f"USER QUERY: {query}\n\n"
        f"RETRIEVED ARTICLE CHUNKS (multiple publishers):\n"
        f"{chunks_text}\n\n"
        f"Produce a balanced cross-publisher summary."
    )
