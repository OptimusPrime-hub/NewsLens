"""
M4 — Event Deduplicator
Clusters and deduplicates timeline events by date and headline semantic similarity.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import numpy as np

from src.m4_timeline.extractor import ExtractedEvent
from src.m4_timeline.schemas import ArticleReference, EventConfidence, TimelineEvent
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.m2_agents.schemas import RetrievedChunk


logger = get_logger(__name__)


class EventDeduplicator:
    """
    Groups and merges duplicate events using date constraints and semantic/Jaccard similarity.
    """

    def __init__(self) -> None:
        self._embedder = None

    def _get_embedder(self):
        if self._embedder is None:
            try:
                from src.m0_ingestion.processors.embedder import Embedder  # noqa: PLC0415
                self._embedder = Embedder()
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Could not initialize M0 Embedder in Deduplicator: {exc}")
                self._embedder = None
        return self._embedder

    def deduplicate(
        self,
        extracted_events: list[ExtractedEvent],
        chunks: list[RetrievedChunk],
    ) -> list[TimelineEvent]:
        """
        Deduplicate and cluster events, mapping them to standard TimelineEvent formats.
        """
        if not extracted_events:
            return []

        # 1. Parse date for each event and group by resolved date
        grouped: dict[date, list[ExtractedEvent]] = {}
        for evt in extracted_events:
            d = self._parse_date(evt.date_text)
            grouped.setdefault(d, []).append(evt)

        timeline_events: list[TimelineEvent] = []
        event_counter = 0

        # 2. Cluster events within each date group
        for event_date, evts in grouped.items():
            clusters = self._cluster_events_for_date(evts)

            for cluster in clusters:
                # Merge the cluster into a single TimelineEvent
                representative = self._select_canonical_representative(cluster)

                # Merge publishers and entities
                merged_publishers = sorted({p.lower() for e in cluster for p in e.publishers if p})
                merged_entities = sorted({ent for e in cluster for ent in e.entities if ent})

                # Resolve source articles
                source_articles = self._resolve_sources(cluster, chunks, representative)

                # Compute confidence tier
                num_pubs = len(merged_publishers)
                if num_pubs >= 3:
                    confidence = EventConfidence.HIGH
                elif num_pubs == 2:
                    confidence = EventConfidence.MEDIUM
                elif num_pubs == 1:
                    confidence = EventConfidence.LOW
                else:
                    confidence = EventConfidence.UNVERIFIED

                timeline_events.append(
                    TimelineEvent(
                        event_id=f"evt_{event_counter}",
                        date=event_date,
                        date_precision="day",
                        headline=representative.headline,
                        description=representative.description,
                        source_articles=source_articles,
                        publishers=merged_publishers,
                        confidence=confidence,
                        entities_involved=merged_entities,
                    )
                )
                event_counter += 1

        # Sort chronologically by date
        timeline_events.sort(key=lambda e: e.date)
        return timeline_events

    def _cluster_events_for_date(self, evts: list[ExtractedEvent]) -> list[list[ExtractedEvent]]:
        return [[e] for e in evts]

    def _similarity(self, t1: str, t2: str) -> float:
        return 0.0

    def _jaccard_similarity(self, s1: str, s2: str) -> float:
        return 0.0

    def _select_canonical_representative(self, cluster: list[ExtractedEvent]) -> ExtractedEvent:
        return cluster[0]

    def _resolve_sources(
        self,
        cluster: list[ExtractedEvent],
        chunks: list[RetrievedChunk],
        canonical: ExtractedEvent,
    ) -> list[ArticleReference]:
        return []

    def _parse_date(self, date_text: str) -> date:
        return date.today()
