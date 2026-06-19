"""
Contract tests for Module 1 intent payloads.
"""

from __future__ import annotations

import json

from src.m1_intent.schemas import IntentPayload, IntentType


def test_m1_intent_payload_contract():
    """Verify IntentPayload matches the schema and can serialize cleanly."""
    payload = IntentPayload(
        intent=IntentType.BIAS_DETECTION,
        entities=["US", "China"],
        publishers=["reuters", "fox"],
        date_range=("2026-06-01", "2026-06-15"),
        raw_query="How did Reuters and Fox cover US-China trade?",
        confidence=0.92,
        topic_keywords=["trade", "tariffs"],
    )

    json_data = payload.model_dump_json()
    parsed = json.loads(json_data)

    assert parsed["intent"] == "BIAS_DETECTION"
    assert parsed["confidence"] == 0.92
    assert parsed["entities"] == ["US", "China"]
    assert parsed["publishers"] == ["reuters", "fox"]
    assert parsed["date_range"] == ["2026-06-01", "2026-06-15"]

    validated = IntentPayload.model_validate_json(json_data)
    assert validated.intent == IntentType.BIAS_DETECTION
    assert validated.confidence == 0.92
    assert validated.date_range == ("2026-06-01", "2026-06-15")
