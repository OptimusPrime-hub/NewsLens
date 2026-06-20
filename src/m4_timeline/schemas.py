from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel


class EventConfidence(StrEnum):
    HIGH = "HIGH"          # ≥ 3 sources confirm
    MEDIUM = "MEDIUM"      # 2 sources confirm
    LOW = "LOW"            # 1 source, corroborated
    UNVERIFIED = "UNVERIFIED"  # 1 source, no corroboration

class ArticleReference(BaseModel):
    title: str
    publisher: str
    url: str
    publish_ts: datetime

class TimelineEvent(BaseModel):
    event_id: str
    date: date
    date_precision: str  # "day" | "week" | "month"
    headline: str
    description: str
    source_articles: list[ArticleReference]
    publishers: list[str]
    confidence: EventConfidence
    entities_involved: list[str]

class TimelineResult(BaseModel):
    topic: str
    events: list[TimelineEvent]  # sorted by date asc
    temporal_gaps: list[tuple[date, date]]
    coherence_score: float
    total_sources_used: int
    date_range_covered: tuple[date, date]
