"""
M1 — Query Intent Classifier
Converts a plain-English query into a validated IntentPayload.

Primary LLM : Groq  llama-3.3-70b-versatile  (fast, cheap, structured output)
Fallback     : Groq  llama-3.1-8b-instant     (smaller, same API)
Final fallback: regex heuristic → CROSS_PUBLISHER_SUMMARY

Pydantic v2 strict validation is applied to every LLM response.
If JSON parsing or validation fails, a regex-based extractor is tried
before defaulting to the safest intent (CROSS_PUBLISHER_SUMMARY).
"""

from __future__ import annotations

import json
import re
import time
from datetime import date, datetime

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from src.shared.config import get_config
from src.m1_intent.prompts import SYSTEM_PROMPT, build_messages
from src.m1_intent.schemas import IntentPayload, IntentType

config = get_config()

_GROQ_PRIMARY_MODEL   = "llama-3.3-70b-versatile"
_GROQ_FALLBACK_MODEL  = "llama-3.1-8b-instant"


# ---------------------------------------------------------------------------
# Groq client (lazy singleton)
# ---------------------------------------------------------------------------

_groq_client = None


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq  # noqa: PLC0415
        _groq_client = Groq(api_key=config.groq_api_key)
    return _groq_client


# ---------------------------------------------------------------------------
# LLM call with retry
# ---------------------------------------------------------------------------

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def _call_groq(messages: list[dict], model: str) -> str:
    """Call Groq chat completions and return the raw text content."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        temperature=0.0,
        max_tokens=512,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` fences if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_payload(raw_json: str, original_query: str) -> IntentPayload:
    """
    Parse raw JSON string → IntentPayload with strict Pydantic validation.
    Raises ValueError on failure (caller handles it).
    """
    data = json.loads(_strip_fences(raw_json))

    # Normalise date_range — convert ["null", "null"] / [None, None] to None
    dr = data.get("date_range")
    if dr and isinstance(dr, (list, tuple)) and len(dr) == 2:
        start, end = dr
        if start and start != "null" and end and end != "null":
            data["date_range"] = (str(start), str(end))
        else:
            data["date_range"] = None
    else:
        data["date_range"] = None

    # Ensure required field
    data["raw_query"] = original_query

    return IntentPayload.model_validate(data)


# ---------------------------------------------------------------------------
# Regex heuristic fallback
# ---------------------------------------------------------------------------

_BIAS_PATTERNS = re.compile(
    r"\b(bias|sentiment|framing|coverage|vs\.?|versus|compare|differ|how did .+ cover)\b",
    re.IGNORECASE,
)
_TIMELINE_PATTERNS = re.compile(
    r"\b(timeline|sequence|chronolog|what happened first|order of events|first|then|after|collapse|crisis)\b",
    re.IGNORECASE,
)


def _heuristic_intent(query: str) -> IntentType:
    if _BIAS_PATTERNS.search(query):
        return IntentType.BIAS_DETECTION
    if _TIMELINE_PATTERNS.search(query):
        return IntentType.TIMELINE
    return IntentType.CROSS_PUBLISHER_SUMMARY


def _regex_fallback(query: str) -> IntentPayload:
    """
    Construct a low-confidence IntentPayload using simple regex patterns.
    Always produces a valid payload so the pipeline never hard-fails at M1.
    """
    intent = _heuristic_intent(query)
    # Extract capitalised word sequences as rough entity candidates
    entities = re.findall(r"[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*", query)
    keywords  = [w.lower() for w in query.split() if len(w) > 3][:8]

    return IntentPayload(
        intent=intent,
        entities=entities[:5],
        publishers=[],
        date_range=None,
        raw_query=query,
        confidence=0.50,
        topic_keywords=keywords,
    )


# ---------------------------------------------------------------------------
# Public classifier
# ---------------------------------------------------------------------------

class IntentClassifier:
    """
    Classifies a natural-language query into an IntentPayload.

    Usage:
        classifier = IntentClassifier()
        payload = classifier.classify("How did BBC vs Fox cover the Gaza war?")
    """

    def classify(self, query: str) -> IntentPayload:
        t0 = time.perf_counter()
        messages = build_messages(query)

        # Try primary Groq model
        for model in (_GROQ_PRIMARY_MODEL, _GROQ_FALLBACK_MODEL):
            try:
                raw = _call_groq(messages, model)
                payload = _parse_payload(raw, query)

                # Enforce confidence threshold → safe fallback
                if payload.confidence < config.m1_confidence_threshold:
                    logger.info(
                        f"[M1] Low confidence {payload.confidence:.2f} < "
                        f"{config.m1_confidence_threshold} → CROSS_PUBLISHER_SUMMARY"
                    )
                    payload = payload.model_copy(
                        update={"intent": IntentType.CROSS_PUBLISHER_SUMMARY}
                    )

                elapsed = time.perf_counter() - t0
                logger.info(
                    f"[M1] Classified '{query[:60]}' → {payload.intent} "
                    f"(conf={payload.confidence:.2f}, model={model}, {elapsed:.2f}s)"
                )
                return payload

            except Exception as exc:
                logger.warning(f"[M1] {model} failed: {exc} — trying next")

        # All LLM paths failed — regex heuristic
        logger.warning(f"[M1] All LLM paths failed for query='{query}' — using regex fallback")
        payload = _regex_fallback(query)
        elapsed = time.perf_counter() - t0
        logger.info(f"[M1] Regex fallback → {payload.intent} ({elapsed:.2f}s)")
        return payload

    async def classify_async(self, query: str) -> IntentPayload:
        """
        Async wrapper — runs the synchronous classify() in a thread pool
        so it can be awaited from FastAPI route handlers.
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.classify, query)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_classifier: IntentClassifier | None = None


def get_classifier() -> IntentClassifier:
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier