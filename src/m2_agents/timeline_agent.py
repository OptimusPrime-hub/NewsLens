"""
Timeline specialist agent node.

Responsibilities:
1. Gather relevant chunks from state.
2. Delegate to M4 TimelineSynthesizer for actual synthesis.
3. Store TimelineResult back into state.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.m2_agents.schemas import TraceEntry
from src.m2_agents.state import AgentState
from src.shared.logging import get_logger

logger = get_logger(__name__)


async def timeline_agent_node(state: AgentState) -> dict:
    """
    Extract temporal events from chunks and delegate to M4 TimelineSynthesizer.
    """
    start = datetime.now(tz=UTC)
    chunks = state.get("relevant_chunks", [])
    payload = state["intent_payload"]

    if not chunks:
        return _empty_result(start, "No relevant chunks for timeline")

    try:
        from src.m4_timeline.synthesizer import TimelineSynthesizer
        synthesizer = TimelineSynthesizer()
        timeline_result = await synthesizer.synthesize(payload.raw_query, chunks)

    except Exception as exc:  # noqa: BLE001
        logger.error("Timeline agent failed", error=str(exc))
        return _empty_result(start, f"Timeline extraction failed: {exc}")

    elapsed = int((datetime.now(tz=UTC) - start).total_seconds() * 1000)

    trace = TraceEntry(
        step_index=state.get("iteration_count", 0) + 1,
        node_name="timeline_agent",
        action="Timeline extraction via M4",
        input_summary=f"{len(chunks)} relevant chunks",
        output_summary=f"{len(timeline_result.events)} events extracted",
        latency_ms=elapsed,
        timestamp=datetime.now(tz=UTC),
    )

    return {
        "timeline_result": timeline_result,
        "agent_trace": [trace],
    }


def _empty_result(start: datetime, reason: str) -> dict:
    """Return an empty timeline result with a warning trace."""
    elapsed = int((datetime.now(tz=UTC) - start).total_seconds() * 1000)
    return {
        "timeline_result": None,
        "agent_trace": [
            TraceEntry(
                step_index=0,
                node_name="timeline_agent",
                action="Timeline extraction skipped",
                input_summary="No chunks available",
                output_summary=reason,
                latency_ms=elapsed,
                timestamp=datetime.now(tz=UTC),
            ),
        ],
        "error_log": [reason],
    }
