"""
Metadata filter builder for retrieval queries.

Translates IntentPayload fields into backend-agnostic filter dicts.
Each retriever adapter maps these to its own query syntax.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.m1_intent.schemas import IntentPayload


@dataclass(frozen=True, slots=True)
class RetrievalFilters:
    """
    Backend-agnostic filter container.

    Retrievers translate these into their native filter syntax.
    """

    publishers: list[str] = field(default_factory=list)
    date_start: str | None = None
    date_end: str | None = None
    entities: list[str] = field(default_factory=list)
    topic_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise non-empty filters to a plain dict."""
        result: dict = {}
        if self.publishers:
            result["publishers"] = self.publishers
        if self.date_start:
            result["date_start"] = self.date_start
        if self.date_end:
            result["date_end"] = self.date_end
        if self.entities:
            result["entities"] = self.entities
        if self.topic_keywords:
            result["topic_keywords"] = self.topic_keywords
        return result


def build_filters(payload: IntentPayload) -> RetrievalFilters:
    """
    Extract retrieval filters from an IntentPayload.

    Args:
        payload: Structured intent from M1.

    Returns:
        A RetrievalFilters instance ready for any retriever.
    """
    date_start = None
    date_end = None
    if payload.date_range:
        date_start, date_end = payload.date_range

    return RetrievalFilters(
        publishers=list(payload.publishers),
        date_start=date_start,
        date_end=date_end,
        entities=list(payload.entities),
        topic_keywords=list(payload.topic_keywords),
    )
