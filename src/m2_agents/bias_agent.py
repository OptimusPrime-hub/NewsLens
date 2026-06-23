"""
Bias specialist agent node.

Gathers relevant chunks from state and delegates analysis to M3 BiasEngine.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.m2_agents.schemas import TraceEntry
from src.m2_agents.state import AgentState
from src.m3_bias.engine import BiasEngine
from src.m3_bias.schemas import BiasAnalysisResult
from src.shared.logging import get_logger

logger = get_logger(__name__)


async def bias_agent_node(state: AgentState) -> dict:
    """Run M3 bias analysis on CRAG-filtered chunks."""
    start = datetime.now(tz=UTC)
    chunks = state.get("relevant_chunks", [])
    payload = state["intent_payload"]

    if not chunks:
        return _empty_result(start, "No relevant chunks for bias analysis")

    engine = BiasEngine(use_fallback_sentiment=True)
    try:
        bias_result = await engine.analyze(payload.raw_query, chunks)
    except Exception as exc:  # noqa: BLE001
        logger.warning("BiasEngine failed", error=str(exc))
        bias_result = BiasAnalysisResult(
            topic=payload.raw_query,
            analysis_timestamp=datetime.now(tz=UTC),
            publisher_profiles=[],
            pairwise_divergence_matrix={},
            summary_explanation=f"Bias analysis failed: {exc}",
            confidence=0.0,
        )

    elapsed = int((datetime.now(tz=UTC) - start).total_seconds() * 1000)

    trace = TraceEntry(
        step_index=state.get("iteration_count", 0) + 1,
        node_name="bias_agent",
        action="Bias analysis via M3 BiasEngine",
        input_summary=f"{len(chunks)} relevant chunks",
        output_summary=f"{len(bias_result.publisher_profiles)} publisher profiles",
        latency_ms=elapsed,
        timestamp=datetime.now(tz=UTC),
    )

    return {
        "bias_result": bias_result,
        "agent_trace": [trace],
    }


def _empty_result(start: datetime, reason: str) -> dict:
    """Return an empty bias result with a warning trace."""
    elapsed = int((datetime.now(tz=UTC) - start).total_seconds() * 1000)
    return {
        "bias_result": None,
        "agent_trace": [
            TraceEntry(
                step_index=0,
                node_name="bias_agent",
                action="Bias analysis skipped",
                input_summary="No chunks available",
                output_summary=reason,
                latency_ms=elapsed,
                timestamp=datetime.now(tz=UTC),
            ),
        ],
        "error_log": [reason],
    }
