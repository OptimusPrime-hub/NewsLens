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
        """
        Groups events into clusters based on headline similarity threshold >= 0.85.
        """
        if not evts:
            return []
        if len(evts) == 1:
            return [[evts[0]]]

        # Simple single-linkage agglomerative clustering
        clusters: list[list[ExtractedEvent]] = [[e] for e in evts]

        changed = True
        while changed:
            changed = False
            best_pair = None
            best_sim = -1.0

            # Find best merge pair
            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    # Compare representatives
                    sim = self._similarity(clusters[i][0].headline, clusters[j][0].headline)
                    if sim >= 0.85 and sim > best_sim:
                        best_sim = sim
                        best_pair = (i, j)

            if best_pair:
                i, j = best_pair
                clusters[i].extend(clusters[j])
                clusters.pop(j)
                changed = True

        return clusters

    def _similarity(self, t1: str, t2: str) -> float:
        """
        Compute similarity score. Uses embedding cosine similarity if available,
        otherwise falls back to Jaccard overlap.
        """
        embedder = self._get_embedder()
        if embedder:
            try:
                vecs = embedder.embed_texts([t1, t2])
                v1, v2 = vecs[0], vecs[1]
                n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
                if n1 > 0 and n2 > 0:
                    return float(np.dot(v1, v2) / (n1 * n2))
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Deduplicator cosine similarity failed: {exc}")

        return self._jaccard_similarity(t1, t2)

    def _jaccard_similarity(self, s1: str, s2: str) -> float:
        w1 = set(re.findall(r"\w+", s1.lower()))
        w2 = set(re.findall(r"\w+", s2.lower()))
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "with", "by", "of", "is", "was", "were", "are", "about", "that", "this",
            "as", "from", "has", "been", "its", "his", "her", "their"
        }
        w1 = w1 - stopwords
        w2 = w2 - stopwords
        if not w1 or not w2:
            return 0.0
        return len(w1 & w2) / len(w1 | w2)

    def _select_canonical_representative(self, cluster: list[ExtractedEvent]) -> ExtractedEvent:
        """Select the event with the longest headline/description as canonical representative."""
        return max(cluster, key=lambda e: len(e.headline) + len(e.description))

    def _resolve_sources(
        self,
        cluster: list[ExtractedEvent],
        chunks: list[RetrievedChunk],
        canonical: ExtractedEvent,
    ) -> list[ArticleReference]:
        """Maps extracted event sources back to retrieved chunks or constructs placeholders."""
        chunk_map = {c.chunk_id: c for c in chunks}
        sources: list[ArticleReference] = []
        seen_urls = set()

        for evt in cluster:
            for cid in evt.chunk_ids_used:
                chunk = chunk_map.get(cid)
                if chunk and chunk.publisher not in seen_urls: # clean duplication guard
                    seen_urls.add(chunk.publisher)
                    sources.append(
                        ArticleReference(
                            title=canonical.headline,
                            publisher=chunk.publisher,
                            url="",  # Fill in if chunk has url, otherwise empty
                            publish_ts=chunk.publish_ts,
                        )
                    )

        # Fallback if no matching chunks found
        if not sources:
            for pub in canonical.publishers:
                sources.append(
                    ArticleReference(
                        title=canonical.headline,
                        publisher=pub,
                        url="",
                        publish_ts=datetime.now(tz=UTC),
                    )
                )
        return sources

    def _parse_date(self, date_text: str) -> date:
        """Best-effort date parsing from free-text."""
        from dateutil import parser as dateutil_parser  # noqa: PLC0415

        try:
            return dateutil_parser.parse(date_text, fuzzy=True).date()
        except (ValueError, TypeError):
            return date.today()
