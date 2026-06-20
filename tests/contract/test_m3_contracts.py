"""
Contract tests to ensure BiasAnalysisResult and PublisherBiasProfile remain compatible
across NewsLens modules (M2, M3, M5).
"""

from __future__ import annotations

from datetime import datetime, timezone
import json

from src.m3_bias.schemas import (
    BiasAnalysisResult,
    FramingVector,
    PublisherBiasProfile,
    SentimentScores,
)


def test_bias_analysis_result_contract():
    """Verify that BiasAnalysisResult satisfies the strict data contract structure."""
    sentiment = SentimentScores(positive=0.4, neutral=0.5, negative=0.1, compound=0.3)
    framing = FramingVector(conflict=0.3, economic=0.2, human_interest=0.1, morality=0.1, responsibility=0.3)
    
    profile = PublisherBiasProfile(
        publisher="Reuters",
        sentiment=sentiment,
        framing=framing,
        entity_salience={"Biden": 0.6, "China": 0.4},
        bias_score=0.15,
        supporting_quotes=["Some quote."],
    )

    result = BiasAnalysisResult(
        topic="US-China trade",
        analysis_timestamp=datetime.now(tz=timezone.utc),
        publisher_profiles=[profile],
        pairwise_divergence_matrix={"Reuters": {"Reuters": 0.0}},
        summary_explanation="Objective overview.",
        confidence=0.8,
    )

    # ── Verify serialization/deserialization cycle ─────────────────────────
    json_data = result.model_dump_json()
    parsed_data = json.loads(json_data)

    # Key fields check
    assert parsed_data["topic"] == "US-China trade"
    assert parsed_data["confidence"] == 0.8
    assert len(parsed_data["publisher_profiles"]) == 1
    assert parsed_data["publisher_profiles"][0]["publisher"] == "Reuters"
    assert parsed_data["publisher_profiles"][0]["bias_score"] == 0.15

    # Re-validate parsed json back into pydantic model
    validated_result = BiasAnalysisResult.model_validate_json(json_data)
    assert validated_result.topic == result.topic
    assert validated_result.publisher_profiles[0].publisher == "Reuters"
    assert validated_result.publisher_profiles[0].sentiment.compound == 0.3
    assert validated_result.publisher_profiles[0].framing.conflict == 0.3
