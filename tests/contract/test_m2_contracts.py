"""
Contract tests for Module 2 orchestration schemas (AnalysisResult).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from src.m1_intent.schemas import IntentType
from src.m2_agents.schemas import AnalysisMetadata, AnalysisResult, SummaryResult, TraceEntry


def test_m2_orchestration_contracts():
    """Verify AnalysisResult and associated sub-schemas serialize and validate correctly."""
    summary = SummaryResult(
        summary_text="Agreement on details.",
        consensus_points=["Item 1"],
        key_takeaways=["Takeaway 1"],
    )

    trace = TraceEntry(
        step_index=1,
        node_name="supervisor",
        action="Routing",
        input_summary="US Trade",
        output_summary="Routed to summary",
        latency_ms=150,
        timestamp=datetime.now(tz=UTC),
    )

    metadata = AnalysisMetadata(
        session_id=uuid4(),
        query_timestamp=datetime.now(tz=UTC),
        total_latency_ms=300,
        retrieval_tier_used="pathway",
        total_chunks_retrieved=10,
        total_chunks_used=6,
        model_versions={"primary": "gpt-4o"},
    )

    result = AnalysisResult(
        intent=IntentType.CROSS_PUBLISHER_SUMMARY,
        raw_query="What happened with trade?",
        summary_result=summary,
        agent_trace=[trace],
        metadata=metadata,
        overall_confidence=0.85,
        warnings=[],
    )

    json_data = result.model_dump_json()
    parsed = json.loads(json_data)

    assert parsed["intent"] == "CROSS_PUBLISHER_SUMMARY"
    assert parsed["overall_confidence"] == 0.85
    assert len(parsed["agent_trace"]) == 1
    assert parsed["summary_result"]["summary_text"] == "Agreement on details."

    validated = AnalysisResult.model_validate_json(json_data)
    assert validated.intent == IntentType.CROSS_PUBLISHER_SUMMARY
    assert validated.summary_result.summary_text == "Agreement on details."
    assert validated.metadata.retrieval_tier_used == "pathway"
