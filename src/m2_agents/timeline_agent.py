"""
Timeline specialist agent node.

Responsibilities:
1. Gather relevant chunks from state.
2. Delegate to M4 TimelineSynthesizer for actual synthesis.
3. Store TimelineResult back into state.

NO timeline logic lives here — M4 owns that.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from src.m2_agents.prompts.timeline import (
    TIMELINE_PREPARATION_SYSTEM_PROMPT,
    build_timeline_user_prompt,
)
from src.m2_agents.schemas import TraceEntry
from src.m2_agents.state import AgentState
from src.m4_timeline.schemas import (
    ArticleReference,
    EventConfidence,
    TimelineEvent,
    TimelineResult,
)
from src.shared.llm_factory import get_chat_model_with_fallback
from src.shared.logging import get_logger

logger = get_logger(__name__)


async def timeline_agent_node(state: AgentState) -> dict:
    """
    Extract temporal events from chunks and delegate to M4.

    In MVP, uses LLM to extract events, then builds a TimelineResult.
    In production, this would call M4's TimelineSynthesizer directly.
    """
    start = datetime.now(tz=timezone.utc)
    chunks = state.get("relevant_chunks", [])
    payload = state["intent_payload"]

    if not chunks:
        return _empty_result(start, "No relevant chunks for timeline")

    # ── Build chunks text ────────────────────────────────────────────────
    chunks_text = _format_chunks(chunks)

    # ── Call LLM for temporal event extraction ───────────────────────────
    try:
        llm = get_chat_model_with_fallback(temperature=0.0)
        messages = [
            SystemMessage(content=TIMELINE_PREPARATION_SYSTEM_PROMPT),
            HumanMessage(content=build_timeline_user_prompt(payload.raw_query, chunks_text)),
        ]
        response = await llm.ainvoke(messages)
        raw_output = response.content

        timeline_result = _parse_timeline_response(raw_output, payload.raw_query)

    except Exception as exc:  # noqa: BLE001
        logger.error("Timeline agent failed", error=str(exc))
        return _empty_result(start, f"Timeline extraction failed: {exc}")

    elapsed = int((datetime.now(tz=timezone.utc) - start).total_seconds() * 1000)

    trace = TraceEntry(
        step_index=state.get("iteration_count", 0) + 1,
        node_name="timeline_agent",
        action="Timeline extraction via M4",
        input_summary=f"{len(chunks)} relevant chunks",
        output_summary=f"{len(timeline_result.events)} events extracted",
        latency_ms=elapsed,
        timestamp=datetime.now(tz=timezone.utc),
    )

    return {
        "timeline_result": timeline_result,
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


def _parse_timeline_response(raw: str, query: str) -> TimelineResult:
    """
    Parse LLM JSON response into TimelineResult.

    Falls back to a minimal result if JSON parsing fails.
    """
    import json

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
            data = {}

    events: list[TimelineEvent] = []
    today = date.today()

    for i, evt in enumerate(data.get("extracted_events", [])):
        event_date = _parse_date(evt.get("date_text", ""))

        refs = [
            ArticleReference(
                title=evt.get("headline", ""),
                publisher=pub,
                url="",
                publish_ts=datetime.now(tz=timezone.utc),
            )
            for pub in evt.get("publishers", ["unknown"])
        ]

        n_publishers = len(evt.get("publishers", []))
        if n_publishers >= 3:
            confidence = EventConfidence.HIGH
        elif n_publishers == 2:
            confidence = EventConfidence.MEDIUM
        else:
            confidence = EventConfidence.LOW

        events.append(
            TimelineEvent(
                event_id=f"evt_{i}",
                date=event_date,
                date_precision="day",
                headline=evt.get("headline", "Unknown event"),
                description=evt.get("description", ""),
                source_articles=refs,
                publishers=evt.get("publishers", []),
                confidence=confidence,
                entities_involved=evt.get("entities", []),
            ),
        )

    # Sort chronologically
    events.sort(key=lambda e: e.date)

    # Compute date range
    if events:
        date_range = (events[0].date, events[-1].date)
    else:
        date_range = (today, today)

    return TimelineResult(
        topic=data.get("topic", query),
        events=events,
        temporal_gaps=[],
        coherence_score=0.7 if events else 0.0,
        total_sources_used=sum(len(e.source_articles) for e in events),
        date_range_covered=date_range,
    )


def _parse_date(date_text: str) -> date:
    """Best-effort date parsing from free-text."""
    from dateutil import parser as dateutil_parser

    try:
        return dateutil_parser.parse(date_text, fuzzy=True).date()
    except (ValueError, TypeError):
        return date.today()


def _empty_result(start: datetime, reason: str) -> dict:
    """Return an empty timeline result with a warning trace."""
    elapsed = int((datetime.now(tz=timezone.utc) - start).total_seconds() * 1000)
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
                timestamp=datetime.now(tz=timezone.utc),
            ),
        ],
        "error_log": [reason],
    }
