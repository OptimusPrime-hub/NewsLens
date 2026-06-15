from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Tuple

class EventConfidence(str, Enum):
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
    temporal_gaps: list[Tuple[date, date]]
    coherence_score: float
    total_sources_used: int
    date_range_covered: Tuple[date, date]
