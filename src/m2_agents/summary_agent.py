"""
Summary specialist agent node.

The ONLY agent allowed to generate directly, because there is no
dedicated M6 summary module. Produces SummaryResult from relevant chunks.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from langchain_core.messages import HumanMessage, SystemMessage

from src.m2_agents.schemas import SummaryResult, TraceEntry
from src.m2_agents.state import AgentState
from src.shared.llm_factory import get_chat_model_with_fallback
from src.shared.logging import get_logger
from src.shared.prompts.summary import (
    SUMMARY_SYSTEM_PROMPT,
    build_summary_user_prompt,
)

logger = get_logger(__name__)


async def summary_agent_node(state: AgentState) -> dict:
    """
    Generate a cross-publisher summary from relevant chunks.

    This is the only specialist that calls the LLM for final
    generation, since no M6 summary module exists.
    """
    start = datetime.now(tz=UTC)
    chunks = state.get("relevant_chunks", [])
    payload = state["intent_payload"]

    if not chunks:
        return _empty_result(start, "No relevant chunks for summary")

    # ── Build chunks text ────────────────────────────────────────────────
    chunks_text = _format_chunks(chunks)

    # ── Call LLM for cross-publisher summary ─────────────────────────────
    try:
        llm = get_chat_model_with_fallback(temperature=0.2, purpose="m5")
        messages = [
            SystemMessage(content=SUMMARY_SYSTEM_PROMPT),
            HumanMessage(content=build_summary_user_prompt(payload.raw_query, chunks_text)),
        ]
        response = await llm.ainvoke(messages)
        summary_result = _parse_summary_response(response.content)

    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Summary agent LLM failed, using offline fallback: {exc}")
        summary_result = _generate_offline_summary(payload.raw_query, chunks)

    elapsed = int((datetime.now(tz=UTC) - start).total_seconds() * 1000)

    trace = TraceEntry(
        step_index=state.get("iteration_count", 0) + 1,
        node_name="summary_agent",
        action="Cross-publisher summary generation",
        input_summary=f"{len(chunks)} relevant chunks",
        output_summary=f"Summary: {len(summary_result.summary_text)} chars",
        latency_ms=elapsed,
        timestamp=datetime.now(tz=UTC),
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


def _generate_offline_summary(query: str, chunks: list) -> SummaryResult:
    """Generate a heuristic/rule-based summary when LLMs are offline."""
    from collections import defaultdict
    pub_chunks = defaultdict(list)
    for c in chunks:
        pub_chunks[c.publisher].append(c.chunk_text.strip())

    summary_parts = []
    summary_parts.append(f"Offline Heuristic Summary for: '{query}'")
    summary_parts.append("All LLM providers are offline. Showing article snippets from scraped sources:")

    key_takeaways = []
    consensus_points = []

    for pub, texts in pub_chunks.items():
        # Take first sentence of first chunk as a takeaway
        sentences = [s.strip() for s in texts[0].split('.') if s.strip()]
        if sentences:
            takeaway = sentences[0]
            if len(takeaway) > 120:
                takeaway = takeaway[:117] + "..."
            key_takeaways.append(f"{pub}: {takeaway}")

        # Add summary section
        summary_parts.append(f"\n[{pub}]")
        for text in texts[:2]:  # top 2 chunks
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            summary_parts.extend(lines[:2])  # top 2 lines of chunk

    summary_text = "\n".join(summary_parts)

    for c in chunks[:3]:
        sentences = [s.strip() for s in c.chunk_text.split('.') if s.strip()]
        if len(sentences) > 1:
            consensus_points.append(sentences[1])

    return SummaryResult(
        summary_text=summary_text,
        consensus_points=consensus_points or ["No high-confidence consensus points identified offline."],
        key_takeaways=key_takeaways or ["Review individual publisher reports below."],
    )


def _empty_result(start: datetime, reason: str) -> dict:
    """Return an empty summary result with a warning trace."""
    elapsed = int((datetime.now(tz=UTC) - start).total_seconds() * 1000)
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
                timestamp=datetime.now(tz=UTC),
            ),
        ],
        "error_log": [reason],
    }
