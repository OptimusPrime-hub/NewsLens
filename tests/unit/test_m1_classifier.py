"""
Unit tests for Module 1 (Query Intent Classifier).
Mocks the LLM calls to test the structured classification,
confidence thresholds, and regex fallbacks offline.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.m1_intent.classifier import IntentClassifier
from src.m1_intent.schemas import IntentPayload, IntentType


@pytest.mark.asyncio
async def test_intent_classifier_success():
    """Verify IntentClassifier succeeds and handles structured output in sync and async."""
    mock_llm = MagicMock()

    # Mock payload returned from LLM
    mock_payload_sync = IntentPayload(
        intent=IntentType.BIAS_DETECTION,
        entities=["OpenAI", "Sam Altman"],
        publishers=["reuters", "foxnews"],
        date_range=None,
        raw_query="Compare OpenAI framing between Reuters and Fox News",
        confidence=0.95,
        topic_keywords=["OpenAI", "Altman"]
    )

    mock_payload_async = IntentPayload(
        intent=IntentType.TIMELINE,
        entities=["SVB"],
        publishers=[],
        date_range=("2023-03-01", "2023-03-31"),
        raw_query="Timeline of SVB collapse",
        confidence=0.98,
        topic_keywords=["SVB", "collapse"]
    )

    mock_structured_llm = MagicMock()
    mock_structured_llm.invoke.return_value = mock_payload_sync
    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_payload_async)

    mock_llm.with_structured_output.return_value = mock_structured_llm

    with patch("src.m1_intent.classifier.get_chat_model_with_fallback", return_value=mock_llm):
        classifier = IntentClassifier()

        # Test synchronous classify
        payload = classifier.classify("Compare OpenAI framing between Reuters and Fox News")
        assert payload.intent == IntentType.BIAS_DETECTION
        assert payload.confidence == 0.95
        assert "OpenAI" in payload.entities
        assert "reuters" in payload.publishers

        # Test asynchronous classify_async
        async_payload = await classifier.classify_async("Timeline of SVB collapse")
        assert async_payload.intent == IntentType.TIMELINE
        assert async_payload.confidence == 0.98
        assert async_payload.date_range == ("2023-03-01", "2023-03-31")


def test_intent_classifier_llm_failure_fallback():
    """Verify IntentClassifier falls back to regex heuristic on LLM exception."""
    mock_llm = MagicMock()
    mock_llm.with_structured_output.side_effect = Exception("API Connection Error")

    with patch("src.m1_intent.classifier.get_chat_model_with_fallback", return_value=mock_llm):
        classifier = IntentClassifier()

        # This contains "bias" -> BIAS_DETECTION
        payload = classifier.classify("What is the bias of BBC coverage?")
        assert payload.intent == IntentType.BIAS_DETECTION
        assert payload.confidence == 0.50  # regex confidence

        # This contains "timeline" -> TIMELINE
        payload2 = classifier.classify("What is the timeline of trade talks?")
        assert payload2.intent == IntentType.TIMELINE
        assert payload2.confidence == 0.50


def test_intent_classifier_low_confidence_coercion():
    """Verify that a low-confidence classification gets coerced to CROSS_PUBLISHER_SUMMARY."""
    mock_llm = MagicMock()
    mock_structured_llm = MagicMock()
    mock_structured_llm.invoke.return_value = IntentPayload(
        intent=IntentType.BIAS_DETECTION,
        entities=[],
        publishers=[],
        date_range=None,
        raw_query="something vague",
        confidence=0.55,  # Below 0.80 threshold
        topic_keywords=[]
    )
    mock_llm.with_structured_output.return_value = mock_structured_llm

    with patch("src.m1_intent.classifier.get_chat_model_with_fallback", return_value=mock_llm):
        classifier = IntentClassifier()
        payload = classifier.classify("something vague")
        # Should be coerced to CROSS_PUBLISHER_SUMMARY due to low confidence
        assert payload.intent == IntentType.CROSS_PUBLISHER_SUMMARY
