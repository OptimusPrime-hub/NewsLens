"""
M4 — Timeline Synthesizer
Orchestrates timeline extraction, deduplication, gap analysis, and coherence scoring.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from src.m4_timeline.deduplicator import EventDeduplicator
from src.m4_timeline.extractor import EventExtractor
from src.m4_timeline.schemas import TimelineResult
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.m2_agents.schemas import RetrievedChunk


logger = get_logger(__name__)


class TimelineSynthesizer:
    """
    Timeline orchestrator: coordinates extraction, deduplication, chronological sorting,
    gap detection, and coherence scoring to produce a validated TimelineResult.
    """

    def __init__(self) -> None:
        self.extractor = EventExtractor()
        self.deduplicator = EventDeduplicator()

    async def synthesize(self, query: str, chunks: list[RetrievedChunk]) -> TimelineResult:
        """
        Asynchronously extract, clean, and synthesize articles into a TimelineResult.
        """
        logger.info("Timeline synthesis started", query=query, chunk_count=len(chunks))

        if not chunks:
            today = date.today()
            return TimelineResult(
                topic=query,
                events=[],
                temporal_gaps=[],
                coherence_score=0.0,
                total_sources_used=0,
                date_range_covered=(today, today),
            )

        # 1. Structured LLM-based event extraction
        extracted_payload = await self.extractor.extract(query, chunks)

        # 2. Grouping and similarity deduplication
        deduplicated_events = self.deduplicator.deduplicate(
            extracted_payload.extracted_events, chunks
        )

        # 3. Detect temporal gaps (> 7 days) and compute coherence
        temporal_gaps = self._detect_temporal_gaps(deduplicated_events)
        coherence_score = self._compute_coherence(deduplicated_events, temporal_gaps)

        # 4. Resolve date range
        if deduplicated_events:
            date_range = (deduplicated_events[0].date, deduplicated_events[-1].date)
        else:
            today = date.today()
            date_range = (today, today)

        total_sources = sum(len(e.source_articles) for e in deduplicated_events)

        logger.info(
            "Timeline synthesis completed",
            event_count=len(deduplicated_events),
            gaps_count=len(temporal_gaps),
            coherence=coherence_score,
        )

        return TimelineResult(
            topic=extracted_payload.topic,
            events=deduplicated_events,
            temporal_gaps=temporal_gaps,
            coherence_score=coherence_score,
            total_sources_used=total_sources,
            date_range_covered=date_range,
        )

    def _detect_temporal_gaps(self, events: list) -> list[tuple[date, date]]:
        """Finds gaps of > 7 days between adjacent chronological events."""
        gaps: list[tuple[date, date]] = []
        if len(events) < 2:
            return gaps

        for i in range(len(events) - 1):
            d1 = events[i].date
            d2 = events[i + 1].date
            diff = (d2 - d1).days
            if diff > 7:
                gaps.append((d1, d2))

        return gaps

    def _compute_coherence(self, events: list, gaps: list) -> float:
        """Coherence = 1.0 - (number of gaps / total events), bounded to [0.0, 1.0]."""
        if not events:
            return 0.0
        n_events = len(events)
        n_gaps = len(gaps)
        score = 1.0 - (n_gaps / n_events)
        return max(0.0, min(1.0, round(score, 2)))
