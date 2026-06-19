"""
Summary specialist agent node.

The ONLY agent allowed to generate directly, because there is no
dedicated M6 summary module. Produces SummaryResult from relevant chunks.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from src.m2_agents.prompts.summary import (
    SUMMARY_SYSTEM_PROMPT,
    build_summary_user_prompt,
)
from src.m2_agents.schemas import SummaryResult, TraceEntry
from src.m2_agents.state import AgentState
from src.shared.llm_factory import get_chat_model_with_fallback
from src.shared.logging import get_logger

logger = get_logger(__name__)


async def summary_agent_node(state: AgentState) -> dict:
    """
    Generate a cross-publisher summary from relevant chunks.

    This is the only specialist that calls the LLM for final
    generation, since no M6 summary module exists.
    """
    start = datetime.now(tz=timezone.utc)
    chunks = state.get("relevant_chunks", [])
    payload = state["intent_payload"]

    if not chunks:
        return _empty_result(start, "No relevant chunks for summary")

    # ── Build chunks text ────────────────────────────────────────────────
    chunks_text = _format_chunks(chunks)

    # ── Call LLM for cross-publisher summary ─────────────────────────────
    try:
        llm = get_chat_model_with_fallback(temperature=0.2)
        messages = [
            SystemMessage(content=SUMMARY_SYSTEM_PROMPT),
            HumanMessage(content=build_summary_user_prompt(payload.raw_query, chunks_text)),
        ]
        response = await llm.ainvoke(messages)
        summary_result = _parse_summary_response(response.content)

    except Exception as exc:  # noqa: BLE001
        logger.error("Summary agent failed", error=str(exc))
        return _empty_result(start, f"Summary generation failed: {exc}")

    elapsed = int((datetime.now(tz=timezone.utc) - start).total_seconds() * 1000)

    trace = TraceEntry(
        step_index=state.get("iteration_count", 0) + 1,
        node_name="summary_agent",
        action="Cross-publisher summary generation",
        input_summary=f"{len(chunks)} relevant chunks",
        output_summary=f"Summary: {len(summary_result.summary_text)} chars",
        latency_ms=elapsed,
        timestamp=datetime.now(tz=timezone.utc),
    )

    return {
        "summary_result": summary_result,
        "agent_trace": [trace],
    }


def _format_chunks(chunks: list) -> str:
    """Format chunks for the LLM prompt."""
    parts: list[str] = []
    for i, chunk in enumerate(chunks):
        parts.append(
            f"[Chunk {i + 1} | Publisher: {chunk.publisher} | "
            f"Date: {chunk.publish_ts.strftime('%Y-%m-%d')} | "
            f"ID: {chunk.chunk_id}]\n{chunk.chunk_text}\n"
        )
    return "\n---\n".join(parts)


def _parse_summary_response(raw: str) -> SummaryResult:
    """Parse LLM JSON response into SummaryResult."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            # Last resort: treat entire response as summary text
            return SummaryResult(
                summary_text=raw.strip(),
                consensus_points=[],
                key_takeaways=[],
            )

    return SummaryResult(
        summary_text=data.get("summary_text", raw),
        consensus_points=data.get("consensus_points", []),
        key_takeaways=data.get("key_takeaways", []),
    )


def _empty_result(start: datetime, reason: str) -> dict:
    """Return an empty summary result with a warning trace."""
    elapsed = int((datetime.now(tz=timezone.utc) - start).total_seconds() * 1000)
    return {
        "summary_result": None,
        "agent_trace": [
            TraceEntry(
                step_index=0,
                node_name="summary_agent",
                action="Summary generation skipped",
                input_summary="No chunks available",
                output_summary=reason,
                latency_ms=elapsed,
                timestamp=datetime.now(tz=timezone.utc),
            ),
        ],
        "error_log": [reason],
    }
