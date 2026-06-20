"""
Supervisor node — entry point and intent-based router.

Responsibilities:
1. Log the initial trace entry.
2. Provide the routing function for conditional edges.

The supervisor does NOT do retrieval or analysis — it only routes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.m1_intent.schemas import IntentType
from src.m2_agents.schemas import TraceEntry
from src.m2_agents.state import AgentState
from src.shared.logging import get_logger

logger = get_logger(__name__)


async def supervisor_node(state: AgentState) -> dict:
    """
    Entry node: logs the received intent and prepares state for routing.

    This node is intentionally thin — routing is handled by the
    conditional edge function `route_by_intent`.
    """
    payload = state["intent_payload"]

    logger.info(
        "Supervisor received query",
        intent=payload.intent.value,
        query=payload.raw_query,
        confidence=payload.confidence,
    )

    trace = TraceEntry(
        step_index=0,
        node_name="supervisor",
        action=f"Route to {payload.intent.value} pipeline",
        input_summary=f"Query: {payload.raw_query[:80]}",
        output_summary=f"Intent: {payload.intent.value} (conf={payload.confidence:.2f})",
        latency_ms=0,
        timestamp=datetime.now(tz=timezone.utc),
    )

    return {
        "agent_trace": [trace],
        "iteration_count": 0,
    }


def route_by_intent(state: AgentState) -> str:
    """
    Conditional edge function — routes to the correct specialist agent.

    Returns the node name that the graph should transition to.
    Low-confidence intents fall back to summary_agent.
    """
    payload = state["intent_payload"]

    # Low confidence → default to summary (safest)
    if payload.confidence < 0.80:
        logger.info("Low confidence, defaulting to summary", confidence=payload.confidence)
        return "summary_agent"

    route_map = {
        IntentType.BIAS_DETECTION: "bias_agent",
        IntentType.TIMELINE: "timeline_agent",
        IntentType.CROSS_PUBLISHER_SUMMARY: "summary_agent",
    }

    target = route_map.get(payload.intent, "summary_agent")
    logger.info("Routing to specialist", target=target)
    return target
