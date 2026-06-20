"""
Contract tests for Module 4 timeline synthesis results.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json

from src.m4_timeline.schemas import (
    ArticleReference,
    EventConfidence,
    TimelineEvent,
    TimelineResult,
)


def test_m4_timeline_contracts():
    """Verify TimelineResult and TimelineEvent contracts."""
    ref = ArticleReference(
        title="Tariffs announced",
        publisher="Reuters",
        url="http://example.com/tariffs",
        publish_ts=datetime.now(tz=timezone.utc),
    )

    event = TimelineEvent(
        event_id="evt_0",
        date=date(2026, 6, 5),
        date_precision="day",
        headline="US imposes tariffs on China",
        description="US announced a new 25% tariff on select Chinese goods.",
        source_articles=[ref],
        publishers=["Reuters"],
        confidence=EventConfidence.LOW,
        entities_involved=["US", "China"],
    )

    result = TimelineResult(
        topic="Trade Talks",
        events=[event],
        temporal_gaps=[(date(2026, 6, 1), date(2026, 6, 5))],
        coherence_score=0.9,
        total_sources_used=1,
        date_range_covered=(date(2026, 6, 5), date(2026, 6, 5)),
    )

    json_data = result.model_dump_json()
    parsed = json.loads(json_data)

    assert parsed["topic"] == "Trade Talks"
    assert len(parsed["events"]) == 1
    assert parsed["events"][0]["headline"] == "US imposes tariffs on China"
    assert parsed["events"][0]["confidence"] == "LOW"

    validated = TimelineResult.model_validate_json(json_data)
    assert validated.topic == "Trade Talks"
    assert validated.events[0].date == date(2026, 6, 5)
    assert validated.events[0].confidence == EventConfidence.LOW
