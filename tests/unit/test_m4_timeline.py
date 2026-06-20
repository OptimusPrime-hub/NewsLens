"""
Unit tests for Module 4 (Timeline Synthesizer).
Mocks the LLM and embedder to test timeline extraction,
deduplication/clustering, chronological sorting, and gap detection offline.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.m2_agents.schemas import RetrievedChunk
from src.m4_timeline.deduplicator import EventDeduplicator
from src.m4_timeline.extractor import EventExtractor, ExtractedEvent, ExtractedTimelinePayload
from src.m4_timeline.schemas import EventConfidence
from src.m4_timeline.synthesizer import TimelineSynthesizer


@pytest.mark.asyncio
async def test_extractor_success():
    """Verify EventExtractor correctly formats chunks and returns structured payload."""
    mock_llm = MagicMock()
    mock_structured_llm = AsyncMock()
    mock_payload = ExtractedTimelinePayload(
        topic="Trade Tariffs",
        extracted_events=[
            ExtractedEvent(
                date_text="2026-06-05",
                headline="Tariffs announced",
                description="US announced tariffs on imports.",
                publishers=["reuters"],
                entities=["US"],
                chunk_ids_used=["c0"],
            )
        ],
    )
    mock_structured_llm.ainvoke.return_value = mock_payload
    mock_llm.with_structured_output.return_value = mock_structured_llm

    with patch("src.m4_timeline.extractor.get_chat_model_with_fallback", return_value=mock_llm):
        extractor = EventExtractor()
        chunks = [
            RetrievedChunk(
                chunk_id="c0",
                chunk_text="US announced tariffs on imports.",
                publisher="reuters",
                publish_ts=datetime(2026, 6, 5, tzinfo=UTC),
                relevance_score=0.9,
            )
        ]
        result = await extractor.extract("trade tariffs", chunks)
        assert result.topic == "Trade Tariffs"
        assert len(result.extracted_events) == 1
        assert result.extracted_events[0].headline == "Tariffs announced"


def test_deduplicator_jaccard_clustering():
    """Test EventDeduplicator clustering events on close headlines using Jaccard fallback."""
    dedup = EventDeduplicator()

    # 2 events on same date with high keyword overlap
    events = [
        ExtractedEvent(
            date_text="2026-06-05",
            headline="OpenAI CEO Sam Altman fired",
            description="Sam Altman was dismissed from OpenAI.",
            publishers=["reuters"],
            entities=["OpenAI", "Altman"],
            chunk_ids_used=["c1"],
        ),
        ExtractedEvent(
            date_text="2026-06-05",
            headline="Sam Altman fired as OpenAI CEO",
            description="Altman has been removed from his position.",
            publishers=["foxnews"],
            entities=["OpenAI", "Altman"],
            chunk_ids_used=["c2"],
        ),
    ]

    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            chunk_text="OpenAI CEO Sam Altman fired.",
            publisher="reuters",
            publish_ts=datetime(2026, 6, 5, tzinfo=UTC),
            relevance_score=0.9,
        ),
        RetrievedChunk(
            chunk_id="c2",
            chunk_text="Sam Altman fired as OpenAI CEO.",
            publisher="foxnews",
            publish_ts=datetime(2026, 6, 5, tzinfo=UTC),
            relevance_score=0.9,
        ),
    ]

    deduplicated = dedup.deduplicate(events, chunks)
    # Both events should be merged into 1 because of high Jaccard similarity and same date
    assert len(deduplicated) == 1
    assert deduplicated[0].date == date(2026, 6, 5)
    assert set(deduplicated[0].publishers) == {"reuters", "foxnews"}
    assert deduplicated[0].confidence == EventConfidence.MEDIUM  # 2 publishers


@pytest.mark.asyncio
async def test_timeline_synthesizer_flow_and_gaps():
    """Verify TimelineResult gap detection, chronological sorting, and coherence score."""
    mock_extractor = AsyncMock()
    mock_extractor.extract.return_value = ExtractedTimelinePayload(
        topic="OpenAI Crisis",
        extracted_events=[
            ExtractedEvent(
                date_text="2023-11-17",
                headline="Sam Altman fired",
                description="Altman was fired.",
                publishers=["reuters"],
                chunk_ids_used=["c1"],
            ),
            # Add an event with > 7 days gap
            ExtractedEvent(
                date_text="2023-11-30",
                headline="Altman returns as CEO",
                description="Altman was reinstated.",
                publishers=["fox"],
                chunk_ids_used=["c2"],
            ),
        ],
    )

    synth = TimelineSynthesizer()
    synth.extractor = mock_extractor

    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            chunk_text="Sam Altman fired.",
            publisher="reuters",
            publish_ts=datetime(2023, 11, 17, tzinfo=UTC),
            relevance_score=0.9,
        ),
        RetrievedChunk(
            chunk_id="c2",
            chunk_text="Altman returns as CEO.",
            publisher="fox",
            publish_ts=datetime(2023, 11, 30, tzinfo=UTC),
            relevance_score=0.9,
        ),
    ]

    result = await synth.synthesize("OpenAI crisis", chunks)
    assert result.topic == "OpenAI Crisis"
    assert len(result.events) == 2
    # Gaps should contain one gap tuple from 2023-11-17 to 2023-11-30 (> 7 days)
    assert len(result.temporal_gaps) == 1
    assert result.temporal_gaps[0] == (date(2023, 11, 17), date(2023, 11, 30))
    # Coherence = 1.0 - (1 gap / 2 events) = 0.50
    assert result.coherence_score == 0.5
