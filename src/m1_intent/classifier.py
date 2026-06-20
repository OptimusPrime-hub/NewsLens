"""
M1 — Query Intent Classifier
Converts a plain-English query into a validated IntentPayload.

Uses the shared LLM factory (OpenAI, Anthropic, or Ollama fallback) and LangChain's
structured output parsing to return a strongly typed IntentPayload.
Final fallback: regex heuristic → CROSS_PUBLISHER_SUMMARY
"""

from __future__ import annotations

import re
import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from loguru import logger

from src.m1_intent.prompts import SYSTEM_PROMPT, build_messages
from src.m1_intent.schemas import IntentPayload, IntentType
from src.shared.config import get_config
from src.shared.llm_factory import get_chat_model_with_fallback

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


def _normalize_payload(payload: IntentPayload, query: str) -> IntentPayload:
    """Normalize payload fields (e.g. date_range) and ensure raw_query is set."""
    dr = payload.date_range
    if dr and len(dr) == 2:
        start, end = dr
        if start and start != "null" and end and end != "null":
            normalized_dr = (str(start), str(end))
        else:
            normalized_dr = None
    else:
        normalized_dr = None

    return payload.model_copy(
        update={"raw_query": query, "date_range": normalized_dr}
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

    def _get_messages(self, query: str) -> list[SystemMessage | HumanMessage | AIMessage]:
        """Format prompt history into LangChain messages."""
        langchain_messages = [SystemMessage(content=SYSTEM_PROMPT)]
        for msg in build_messages(query):
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
        return langchain_messages

    def classify(self, query: str) -> IntentPayload:
        t0 = time.perf_counter()
        config = get_config()

        try:
            llm = get_chat_model_with_fallback(temperature=0.0)
            structured_llm = llm.with_structured_output(IntentPayload)

            messages = self._get_messages(query)
            payload = structured_llm.invoke(messages)
            payload = _normalize_payload(payload, query)

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
                f"(conf={payload.confidence:.2f}, {elapsed:.2f}s)"
            )
            return payload

        except Exception as exc:
            logger.warning(f"[M1] LLM classification failed: {exc} — trying regex fallback")

        # All LLM paths failed — regex heuristic fallback
        payload = _regex_fallback(query)
        elapsed = time.perf_counter() - t0
        logger.info(f"[M1] Regex fallback → {payload.intent} ({elapsed:.2f}s)")
        return payload

    async def classify_async(self, query: str) -> IntentPayload:
        """
        Async version of classify.
        """
        t0 = time.perf_counter()
        config = get_config()

        try:
            llm = get_chat_model_with_fallback(temperature=0.0)
            structured_llm = llm.with_structured_output(IntentPayload)

            messages = self._get_messages(query)
            payload = await structured_llm.ainvoke(messages)
            payload = _normalize_payload(payload, query)

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
                f"(conf={payload.confidence:.2f}, {elapsed:.2f}s)"
            )
            return payload

        except Exception as exc:
            logger.warning(f"[M1] LLM classification failed: {exc} — trying regex fallback")

        # Fallback
        payload = _regex_fallback(query)
        elapsed = time.perf_counter() - t0
        logger.info(f"[M1] Regex fallback → {payload.intent} ({elapsed:.2f}s)")
        return payload


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_classifier: IntentClassifier | None = None


def get_classifier() -> IntentClassifier:
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier
