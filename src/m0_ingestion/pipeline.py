"""
M0 — Pipeline
Assembles the live ingestion pipeline:
  NewsAPI connector + RSS connector
  → Normalizer → Chunker → Embedder
  → in-process chunk store (used by LocalRetriever on Windows)

Pathway VectorStore indexing runs separately via:
  scripts/sync_news_sources.py → scripts/run_pathway_pipeline.py
"""

from __future__ import annotations

import threading
import time

from loguru import logger

from src.m0_ingestion.connectors.newsapi_connector import NewsAPIConnector
from src.m0_ingestion.connectors.rss_connector import RSSConnector
from src.m0_ingestion.document_store import document_store
from src.m0_ingestion.processors.chunker import SemanticChunker
from src.m0_ingestion.processors.embedder import Embedder
from src.m0_ingestion.processors.normalizer import ArticleNormalizer
from src.m0_ingestion.schemas import ArticleChunk, NormalizedArticle, RawArticle
from src.shared.config import get_config

config = get_config()


class IngestionPipeline:
    """
    Orchestrates the M0 in-process ingestion pipeline.

    Populates an in-memory chunk store for LocalRetriever. Pathway indexing
    is handled by scripts/run_pathway_pipeline.py over synced JSON files.
    """

    def __init__(self, default_query: str = "world news top stories") -> None:
        self.default_query = default_query
        self.normalizer = ArticleNormalizer()
        self.chunker = SemanticChunker()
        self.embedder = Embedder()
        self._newsapi = NewsAPIConnector()
        self._rss = RSSConnector()
        self._running = False

        # In-process chunk store for when Pathway VectorStore is unavailable
        self._chunk_store: list[tuple[ArticleChunk, list[float]]] = []
        self._chunk_lock = threading.Lock()

        # Try to set up Pathway
        self._pathway_server = None
        self._try_init_pathway()

    # ------------------------------------------------------------------
    # Pathway setup (optional)
    # ------------------------------------------------------------------

    def _try_init_pathway(self) -> None:
        from src.m2_agents.retrieval.runtime import use_pathway_primary

        if use_pathway_primary():
            logger.info("[Pipeline] Pathway available — use run_pathway_pipeline.py for VectorStore")
            self._use_pathway = True
        else:
            logger.info("[Pipeline] Using in-process chunk store (Pathway runs in Docker on Windows)")
            self._use_pathway = False

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def _process_raw_articles(self, raws: list[RawArticle]) -> None:
        """Normalize → chunk → embed → store."""
        if not raws:
            return

        articles: list[NormalizedArticle] = self.normalizer.normalize_batch(raws)
        if not articles:
            return

        document_store.add_batch(articles)

        chunks: list[ArticleChunk] = self.chunker.chunk_batch(articles)
        if not chunks:
            return

        embedded = self.embedder.embed_chunks(chunks)

        with self._chunk_lock:
            for chunk, vec in embedded:
                self._chunk_store.append((chunk, vec.tolist()))

        logger.info(
            f"[Pipeline] Processed {len(articles)} articles → "
            f"{len(chunks)} chunks → "
            f"total store size: {len(self._chunk_store)}"
        )

    # ------------------------------------------------------------------
    # Poll loop (used when Pathway pw.run() is not available)
    # ------------------------------------------------------------------

    def _poll_once(self) -> None:
        """Single poll cycle: NewsAPI + RSS."""
        start = time.perf_counter()
        newsapi_articles = self._newsapi.fetch(self.default_query)
        rss_articles = self._rss.fetch_all()
        self._process_raw_articles(newsapi_articles + rss_articles)
        elapsed = time.perf_counter() - start
        logger.info(f"[Pipeline] Poll cycle completed in {elapsed:.1f}s")

    def _poll_loop(self) -> None:
        """Background thread poll loop."""
        while self._running:
            try:
                self._poll_once()
            except Exception as exc:
                logger.error(f"[Pipeline] Poll error: {exc}")
            time.sleep(config.pathway_refresh_interval_ms / 1000)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_background(self) -> threading.Thread:
        """
        Start the ingestion loop in a daemon background thread.
        Returns the thread so the caller can join/monitor it.
        """
        self._running = True
        # Run one cycle immediately before returning
        self._poll_once()

        thread = threading.Thread(target=self._poll_loop, daemon=True, name="m0-ingestion")
        thread.start()
        logger.info("[Pipeline] Background ingestion thread started")
        return thread

    def stop(self) -> None:
        self._running = False
        logger.info("[Pipeline] Ingestion pipeline stopped")

    def run(self) -> None:
        """
        Blocking run — starts the pipeline and never returns.
        Called by scripts/run_pathway_pipeline.py.
        """
        logger.info("[Pipeline] Starting blocking ingestion loop")
        self._running = True
        self._poll_once()
        self._poll_loop()

    # ------------------------------------------------------------------
    # In-process retrieval (used by M2 when Pathway VectorStore is absent)
    # ------------------------------------------------------------------

    def similarity_search(
        self, query_vec: list[float], top_k: int = 15
    ) -> list[tuple[ArticleChunk, float]]:
        """
        Cosine similarity search over the in-process chunk store.
        Returns (chunk, score) pairs sorted descending by score.
        """
        import numpy as np

        q = np.array(query_vec, dtype=np.float32)
        q_norm = q / (np.linalg.norm(q) + 1e-9)

        with self._chunk_lock:
            store_snapshot = list(self._chunk_store)

        if not store_snapshot:
            return []

        matrix = np.array([v for _, v in store_snapshot], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9
        normed = matrix / norms
        scores = normed @ q_norm

        top_idx = scores.argsort()[::-1][:top_k]
        return [(store_snapshot[i][0], float(scores[i])) for i in top_idx]

    @property
    def chunk_count(self) -> int:
        return len(self._chunk_store)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_pipeline: IngestionPipeline | None = None


def get_pipeline(query: str = "world news top stories") -> IngestionPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = IngestionPipeline(default_query=query)
    return _pipeline
