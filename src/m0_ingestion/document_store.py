"""
M0 — Document Store
Lightweight in-process metadata store for NormalizedArticle records.
Allows M2 to look up full article metadata (publisher, URL, timestamp)
by article_id without querying the VectorStore.

In production this would be backed by a Pathway DocumentStore; here we
use a thread-safe dict for simplicity and Pathway compatibility.
"""

from __future__ import annotations

import threading
from datetime import datetime

from loguru import logger

from src.m0_ingestion.schemas import NormalizedArticle


class DocumentStore:
    """
    Thread-safe key→NormalizedArticle registry.
    Keyed by article_id (URL fingerprint from normalizer.py).
    """

    def __init__(self) -> None:
        self._store: dict[str, NormalizedArticle] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------

    def add(self, article: NormalizedArticle) -> None:
        with self._lock:
            self._store[article.article_id] = article

    def add_batch(self, articles: list[NormalizedArticle]) -> None:
        with self._lock:
            for a in articles:
                self._store[a.article_id] = a
        logger.debug(f"[DocumentStore] Added {len(articles)} articles — total={len(self._store)}")

    def get(self, article_id: str) -> NormalizedArticle | None:
        return self._store.get(article_id)

    def all(self) -> list[NormalizedArticle]:
        with self._lock:
            return list(self._store.values())

    def filter_by_publisher(self, publisher: str) -> list[NormalizedArticle]:
        return [a for a in self.all() if a.publisher == publisher]

    def filter_by_date_range(
        self, start: datetime, end: datetime
    ) -> list[NormalizedArticle]:
        return [a for a in self.all() if start <= a.publish_ts <= end]

    def publishers(self) -> list[str]:
        return sorted({a.publisher for a in self.all()})

    def __len__(self) -> int:
        return len(self._store)


# ---------------------------------------------------------------------------
# Module-level singleton — import and use directly
# ---------------------------------------------------------------------------
document_store = DocumentStore()
