from enum import StrEnum

from pydantic import BaseModel, Field


class IntentType(StrEnum):
    TIMELINE = "TIMELINE"
    BIAS_DETECTION = "BIAS_DETECTION"
    CROSS_PUBLISHER_SUMMARY = "CROSS_PUBLISHER_SUMMARY"

class IntentPayload(BaseModel):
    intent: IntentType
    entities: list[str] = Field(default_factory=list)
    publishers: list[str] = Field(default_factory=list)
    date_range: tuple[str, str] | None = None
    raw_query: str
    confidence: float = Field(ge=0.0, le=1.0)
    topic_keywords: list[str] = Field(default_factory=list)
