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
        if not timeline_result.events and chunks:
            logger.warning("Timeline LLM synthesis returned 0 events; using offline fallback")
            timeline_result = _generate_offline_timeline(payload.raw_query, chunks)

    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Timeline agent LLM synthesis failed, using offline fallback: {exc}")
        timeline_result = _generate_offline_timeline(payload.raw_query, chunks)

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


def _generate_offline_timeline(query: str, chunks: list) -> TimelineResult:
    """Generate a chronological timeline of events when LLMs are offline."""
    from datetime import date, datetime
    from src.m4_timeline.schemas import TimelineResult, TimelineEvent, ArticleReference, EventConfidence
    
    # Sort chunks by publication timestamp ascending
    sorted_chunks = sorted(chunks, key=lambda c: c.publish_ts or datetime.min)
    
    events = []
    for idx, chunk in enumerate(sorted_chunks):
        event_date = chunk.publish_ts.date() if chunk.publish_ts else date.today()
        
        # Heuristic headline: first sentence or first 10 words
        sentences = [s.strip() for s in chunk.chunk_text.split('.') if s.strip()]
        headline = sentences[0] if sentences else "Event reported"
        if len(headline) > 60:
            headline = headline[:57] + "..."
            
        description = sentences[0] if sentences else chunk.chunk_text[:100]
        
        ref = ArticleReference(
            title=headline,
            publisher=chunk.publisher or "Unknown",
            url=chunk.source_url or "",
            publish_ts=chunk.publish_ts or datetime.now()
        )
        
        event = TimelineEvent(
            event_id=f"evt_offline_{idx}",
            date=event_date,
            date_precision="day",
            headline=headline,
            description=description,
            source_articles=[ref],
            publishers=[chunk.publisher or "Unknown"],
            confidence=EventConfidence.UNVERIFIED,
            entities_involved=[]
        )
        events.append(event)
        
    events = events[:15]
    
    # Find gaps (> 7 days)
    gaps = []
    if len(events) > 1:
        for i in range(len(events) - 1):
            d1 = events[i].date
            d2 = events[i + 1].date
            if (d2 - d1).days > 7:
                gaps.append((d1, d2))
                
    coherence = 1.0 - (len(gaps) / len(events)) if events else 0.0
    
    if events:
        date_range = (events[0].date, events[-1].date)
    else:
        today = date.today()
        date_range = (today, today)
        
    return TimelineResult(
        topic=query,
        events=events,
        temporal_gaps=gaps,
        coherence_score=max(0.0, coherence),
        total_sources_used=len(chunks),
        date_range_covered=date_range
    )


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
