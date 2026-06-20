"""
M1 — Prompt Templates
Few-shot prompts for LLM-based intent classification.
Groq (llama-3.3-70b-versatile) is the primary LLM; structured JSON output
is enforced via a system prompt that demands strict JSON-only responses.
"""

from __future__ import annotations

SYSTEM_PROMPT = """\
You are a news query intent classifier for the NewsLens platform.
Your ONLY job is to parse a user's natural language query and return a
single JSON object — no preamble, no explanation, no markdown fences.

The JSON must conform exactly to this schema:
{
  "intent": "<BIAS_DETECTION | TIMELINE | CROSS_PUBLISHER_SUMMARY>",
  "entities": ["<named entities — people, orgs, places, events>"],
  "publishers": ["<canonical lowercase publisher slugs if mentioned>"],
  "date_range": ["<YYYY-MM-DD start or null>", "<YYYY-MM-DD end or null>"],
  "topic_keywords": ["<3-8 salient topic keywords>"],
  "confidence": <float 0.0–1.0>
}

Intent selection rules:
- BIAS_DETECTION   → query compares publishers, asks about sentiment/framing/coverage bias
- TIMELINE         → query asks about sequence of events, chronology, "what happened first"
- CROSS_PUBLISHER_SUMMARY → general "what is happening with X", summary across sources

If confidence < 0.80, set intent to "CROSS_PUBLISHER_SUMMARY" (safest fallback).
Publishers must be lowercase slugs: reuters, bbc, foxnews, cnn, aljazeera, nyt,
guardian, washingtonpost, ap, npr, or the lowercased name if not in that list.
date_range: use null for unknown dates.
Return ONLY the JSON object. No other text.
"""

FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": "How did Reuters and Fox News cover the US-China trade talks differently?",
    },
    {
        "role": "assistant",
        "content": """{
  "intent": "BIAS_DETECTION",
  "entities": ["United States", "China", "trade talks"],
  "publishers": ["reuters", "foxnews"],
  "date_range": [null, null],
  "topic_keywords": ["US-China", "trade", "tariffs", "trade talks", "coverage"],
  "confidence": 0.97
}""",
    },
    {
        "role": "user",
        "content": "Timeline of the Silicon Valley Bank collapse",
    },
    {
        "role": "assistant",
        "content": """{
  "intent": "TIMELINE",
  "entities": ["Silicon Valley Bank", "SVB"],
  "publishers": [],
  "date_range": ["2023-03-01", "2023-03-31"],
  "topic_keywords": ["Silicon Valley Bank", "SVB", "bank run", "FDIC", "collapse", "2023"],
  "confidence": 0.96
}""",
    },
    {
        "role": "user",
        "content": "What is happening with the Gaza ceasefire negotiations?",
    },
    {
        "role": "assistant",
        "content": """{
  "intent": "CROSS_PUBLISHER_SUMMARY",
  "entities": ["Gaza", "ceasefire"],
  "publishers": [],
  "date_range": [null, null],
  "topic_keywords": ["Gaza", "ceasefire", "negotiations", "peace talks", "Middle East"],
  "confidence": 0.92
}""",
    },
    {
        "role": "user",
        "content": "Compare BBC and Al Jazeera sentiment toward the Ukraine war",
    },
    {
        "role": "assistant",
        "content": """{
  "intent": "BIAS_DETECTION",
  "entities": ["Ukraine", "Russia", "Ukraine war"],
  "publishers": ["bbc", "aljazeera"],
  "date_range": [null, null],
  "topic_keywords": ["Ukraine", "Russia", "war", "sentiment", "coverage", "framing"],
  "confidence": 0.98
}""",
    },
    {
        "role": "user",
        "content": "What happened first during the OpenAI board crisis?",
    },
    {
        "role": "assistant",
        "content": """{
  "intent": "TIMELINE",
  "entities": ["OpenAI", "Sam Altman"],
  "publishers": [],
  "date_range": ["2023-11-01", "2023-12-31"],
  "topic_keywords": ["OpenAI", "board", "Sam Altman", "firing", "reinstatement", "crisis"],
  "confidence": 0.95
}""",
    },
]


def build_messages(user_query: str) -> list[dict]:
    """
    Build the full messages array for the classification API call,
    including the system prompt and few-shot examples.
    """
    messages: list[dict] = []

    # Inject few-shot examples as user/assistant turns
    messages.extend(FEW_SHOT_EXAMPLES)

    # The actual query
    messages.append({"role": "user", "content": user_query})
    return messages