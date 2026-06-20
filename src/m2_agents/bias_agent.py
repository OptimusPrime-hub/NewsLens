"""
Bias specialist agent node.

Responsibilities:
1. Gather relevant chunks from state.
2. Delegate to M3 BiasEngine for actual analysis.
3. Store BiasAnalysisResult back into state.

NO bias computation logic lives here — M3 owns that.
"""

from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from src.m2_agents.prompts.bias import (
    BIAS_PREPARATION_SYSTEM_PROMPT,
    build_bias_user_prompt,
)
from src.m2_agents.schemas import TraceEntry
from src.m2_agents.state import AgentState
from src.m3_bias.schemas import (
    BiasAnalysisResult,
    FramingVector,
    PublisherBiasProfile,
    SentimentScores,
)
from src.shared.llm_factory import get_chat_model_with_fallback
from src.shared.logging import get_logger

logger = get_logger(__name__)


async def bias_agent_node(state: AgentState) -> dict:
    """
    Prepare chunks and delegate to M3 for bias analysis.

    In MVP, uses LLM to extract per-publisher bias indicators
    from the relevant chunks, then builds a BiasAnalysisResult.
    In production, this would call M3's BiasEngine directly.
    """
    start = datetime.now(tz=timezone.utc)
    chunks = state.get("relevant_chunks", [])
    payload = state["intent_payload"]

    if not chunks:
        return _empty_result(start, "No relevant chunks for bias analysis")

    # ── Build chunks text for LLM ────────────────────────────────────────
    chunks_text = _format_chunks(chunks)

    # ── Call LLM to prepare bias indicators ──────────────────────────────
    try:
        llm = get_chat_model_with_fallback(temperature=0.0)
        messages = [
            SystemMessage(content=BIAS_PREPARATION_SYSTEM_PROMPT),
            HumanMessage(content=build_bias_user_prompt(payload.raw_query, chunks_text)),
        ]
        response = await llm.ainvoke(messages)
        raw_output = response.content

        # ── Parse and delegate to M3 schema ──────────────────────────────
        bias_result = _parse_bias_response(raw_output, payload.raw_query)

    except Exception as exc:  # noqa: BLE001
        logger.error("Bias agent failed", error=str(exc))
        return _empty_result(start, f"Bias analysis failed: {exc}")

    elapsed = int((datetime.now(tz=timezone.utc) - start).total_seconds() * 1000)

    trace = TraceEntry(
        step_index=state.get("iteration_count", 0) + 1,
        node_name="bias_agent",
        action="Bias analysis via M3",
        input_summary=f"{len(chunks)} relevant chunks",
        output_summary=f"{len(bias_result.publisher_profiles)} publisher profiles",
        latency_ms=elapsed,
        timestamp=datetime.now(tz=timezone.utc),
    )

    return {
        "bias_result": bias_result,
        "agent_trace": [trace],
    }


def _format_chunks(chunks: list) -> str:
    """Format chunks into a text block for the LLM prompt."""
    parts: list[str] = []
    for i, chunk in enumerate(chunks):
        parts.append(
            f"[Chunk {i + 1} | Publisher: {chunk.publisher} | "
            f"Date: {chunk.publish_ts.strftime('%Y-%m-%d')} | "
            f"ID: {chunk.chunk_id}]\n{chunk.chunk_text}\n"
        )
    return "\n---\n".join(parts)


def _parse_bias_response(raw: str, query: str) -> BiasAnalysisResult:
    """
    Parse LLM JSON response into BiasAnalysisResult.

    Falls back to a minimal result if JSON parsing fails.
    """
    import json

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown fences
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            data = {}

    profiles: list[PublisherBiasProfile] = []
    for summary in data.get("publisher_summaries", []):
        profiles.append(
            PublisherBiasProfile(
                publisher=summary.get("publisher", "unknown"),
                sentiment=SentimentScores(
                    positive=0.0, neutral=1.0, negative=0.0, compound=0.0,
                ),
                framing=FramingVector(
                    conflict=0.2, economic=0.2, human_interest=0.2,
                    morality=0.2, responsibility=0.2,
                ),
                entity_salience={},
                bias_score=0.0,
                supporting_quotes=summary.get("emotionally_charged_phrases", []),
            ),
        )

    return BiasAnalysisResult(
        topic=data.get("topic", query),
        analysis_timestamp=datetime.now(tz=timezone.utc),
        publisher_profiles=profiles,
        pairwise_divergence_matrix={},
        summary_explanation=data.get("cross_publisher_observations", ""),
        confidence=0.6 if profiles else 0.0,
    )


def _empty_result(start: datetime, reason: str) -> dict:
    """Return an empty bias result with a warning trace."""
    elapsed = int((datetime.now(tz=timezone.utc) - start).total_seconds() * 1000)
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
                timestamp=datetime.now(tz=timezone.utc),
            ),
        ],
        "error_log": [reason],
    }
