"""
Result assembly node — the ONLY place that builds AnalysisResult.

Reads all intermediate outputs from state and assembles the final
AnalysisResult. This centralisation means only one file needs to
change if the AnalysisResult schema evolves.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from src.m2_agents.schemas import AnalysisMetadata, AnalysisResult, TraceEntry
from src.m2_agents.state import AgentState
from src.shared.llm_factory import get_active_model_name
from src.shared.logging import get_logger

logger = get_logger(__name__)


async def assemble_result_node(state: AgentState) -> dict:
    """
    Build the final AnalysisResult from state intermediates.

    This is the single point of truth for result construction.
    """
    start = datetime.now(tz=UTC)
    payload = state["intent_payload"]
    trace_entries = state.get("agent_trace", [])
    error_log = state.get("error_log", [])

    # ── Compute overall confidence ───────────────────────────────────────
    confidence = _compute_confidence(state)

    # ── Compute total latency from trace ─────────────────────────────────
    total_latency = sum(t.latency_ms for t in trace_entries)

    # ── Count chunks ─────────────────────────────────────────────────────
    retrieved = state.get("retrieved_chunks", [])
    relevant = state.get("relevant_chunks", [])

    # ── Build metadata ───────────────────────────────────────────────────
    metadata = AnalysisMetadata(
        session_id=uuid4(),
        query_timestamp=start,
        total_latency_ms=total_latency,
        retrieval_tier_used=state.get("retrieval_tier", "unknown"),
        total_chunks_retrieved=len(retrieved),
        total_chunks_used=len(relevant),
        model_versions={"primary": get_active_model_name()},
    )

    # ── Assembly trace entry ─────────────────────────────────────────────
    elapsed = int((datetime.now(tz=UTC) - start).total_seconds() * 1000)
    assembly_trace = TraceEntry(
        step_index=len(trace_entries) + 1,
        node_name="assembler",
        action="Final result assembly",
        input_summary=(
            f"bias={state.get('bias_result') is not None}, "
            f"timeline={state.get('timeline_result') is not None}, "
            f"summary={state.get('summary_result') is not None}"
        ),
        output_summary=f"confidence={confidence:.2f}, warnings={len(error_log)}",
        latency_ms=elapsed,
        timestamp=datetime.now(tz=UTC),
    )

    # ── Build warnings list ──────────────────────────────────────────────
    warnings = [e for e in error_log if e.startswith("VALIDATION:")]

    # ── Assemble final result ────────────────────────────────────────────
    result = AnalysisResult(
        intent=payload.intent,
        raw_query=payload.raw_query,
        bias_result=state.get("bias_result"),
        timeline_result=state.get("timeline_result"),
        summary_result=state.get("summary_result"),
        agent_trace=trace_entries + [assembly_trace],
        metadata=metadata,
        overall_confidence=confidence,
        warnings=warnings,
    )

    logger.info(
        "Result assembled",
        intent=payload.intent.value,
        confidence=confidence,
        n_warnings=len(warnings),
    )

    # We store the final result in a separate key for the graph output
    return {
        "agent_trace": [assembly_trace],
        "_final_result": result,
    }


def _compute_confidence(state: AgentState) -> float:
    """
    Compute overall confidence from available signals.

    Factors:
    - Intent classifier confidence
    - Ratio of relevant chunks to total retrieved
    - Whether the expected result was produced
    """
    scores: list[float] = []

    # Intent confidence
    scores.append(state["intent_payload"].confidence)

    # Retrieval quality
    retrieved = state.get("retrieved_chunks", [])
    relevant = state.get("relevant_chunks", [])
    if retrieved:
        scores.append(len(relevant) / len(retrieved))
    else:
        scores.append(0.0)

    # Result completeness
    intent = state["intent_payload"].intent
    if intent.value == "BIAS_DETECTION":
        scores.append(1.0 if state.get("bias_result") else 0.0)
    elif intent.value == "TIMELINE":
        scores.append(1.0 if state.get("timeline_result") else 0.0)
    else:
        scores.append(1.0 if state.get("summary_result") else 0.0)

    return round(sum(scores) / len(scores), 2) if scores else 0.0
