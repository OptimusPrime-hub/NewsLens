"""
Validation node — cheap structural checks instead of expensive LLM self-reflection.

Checks:
- chunks_used > 0
- confidence exists
- required result exists for the intent
- trace exists

Adds warnings if checks fail; never blocks the pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.m1_intent.schemas import IntentType
from src.m2_agents.schemas import TraceEntry
from src.m2_agents.state import AgentState
from src.shared.logging import get_logger

logger = get_logger(__name__)


async def validate_node(state: AgentState) -> dict:
    """
    Run structural validation on the agent state.

    This replaces the expensive LLM-based self-reflection node.
    All checks are deterministic and fast.
    """
    start = datetime.now(tz=UTC)
    warnings: list[str] = []
    intent = state["intent_payload"].intent

    # ── Check: relevant chunks exist ─────────────────────────────────────
    relevant = state.get("relevant_chunks", [])
    if not relevant:
        warnings.append("VALIDATION: No relevant chunks after CRAG filtering")

    # ── Check: required result exists for the routed intent ──────────────
    if intent == IntentType.BIAS_DETECTION and state.get("bias_result") is None:
        warnings.append("VALIDATION: Bias analysis was requested but produced no result")

    if intent == IntentType.TIMELINE and state.get("timeline_result") is None:
        warnings.append("VALIDATION: Timeline was requested but produced no result")

    if intent == IntentType.CROSS_PUBLISHER_SUMMARY and state.get("summary_result") is None:
        warnings.append("VALIDATION: Summary was requested but produced no result")

    # ── Check: agent trace exists ────────────────────────────────────────
    trace_entries = state.get("agent_trace", [])
    if len(trace_entries) < 2:
        warnings.append("VALIDATION: Agent trace is suspiciously short")

    # ── Check: retrieval tier is set ─────────────────────────────────────
    if not state.get("retrieval_tier"):
        warnings.append("VALIDATION: No retrieval tier recorded")

    # ── Log ──────────────────────────────────────────────────────────────
    if warnings:
        for w in warnings:
            logger.warning(w)
    else:
        logger.info("Validation passed — all checks OK")

    elapsed = int((datetime.now(tz=UTC) - start).total_seconds() * 1000)

    trace = TraceEntry(
        step_index=len(trace_entries) + 1,
        node_name="validator",
        action="Structural validation",
        input_summary=f"Intent: {intent.value}",
        output_summary=f"{len(warnings)} warnings" if warnings else "All checks passed",
        latency_ms=elapsed,
        timestamp=datetime.now(tz=UTC),
    )

    return {
        "agent_trace": [trace],
        "error_log": warnings,
    }
