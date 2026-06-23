"""
Retrieval orchestrator with tiered fallback cascade.

RetrievalManager owns ONLY the orchestration logic:
  Tier 0: Pathway VectorStore (Linux/Docker) or LocalRetriever (Windows)
  Tier 1: Query rewrite + primary retry
  Tier 2: Tavily AI Search
  Tier 3: Web scraper

Each BaseRetriever handles its own HTTP/retry concerns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.m2_agents.retrieval.base import BaseRetriever
from src.m2_agents.retrieval.tavily_client import TavilyRetriever
from src.m2_agents.retrieval.local_client import LocalRetriever
from src.m2_agents.retrieval.pathway_client import PathwayRetriever
from src.m2_agents.retrieval.runtime import use_pathway_primary
from src.m2_agents.retrieval.scraper_client import ScraperRetriever
from src.m2_agents.schemas import RetrievedChunk
from src.shared.config import get_settings
from src.shared.exceptions import FallbackExhaustedError, RetrievalError
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.m2_agents.crag.rewriter import QueryRewriter
    from src.m2_agents.retrieval.filters import RetrievalFilters

logger = get_logger(__name__)


def _default_retrievers() -> tuple[BaseRetriever, BaseRetriever, BaseRetriever]:
    """Pick the primary retriever based on platform and installed backends."""
    if use_pathway_primary():
        return PathwayRetriever(), TavilyRetriever(), ScraperRetriever()
    logger.info("Using in-process LocalRetriever as primary (Pathway unavailable)")
    return LocalRetriever(), TavilyRetriever(), ScraperRetriever()


class RetrievalManager:
    """
    Orchestrates the retrieval fallback cascade.

    Usage:
        manager = RetrievalManager(rewriter=query_rewriter)
        chunks, tier = await manager.retrieve(query, filters)
    """

    def __init__(
        self,
        *,
        rewriter: QueryRewriter | None = None,
        retrievers: list[BaseRetriever] | None = None,
    ) -> None:
        settings = get_settings()
        self._threshold = settings.crag_relevance_threshold
        self._top_k = settings.retrieval_top_k
        self._rewriter = rewriter

        # Default retriever chain (can be overridden for testing)
        if retrievers is not None:
            self._primary = retrievers[0] if len(retrievers) > 0 else PathwayRetriever()
            self._secondary = retrievers[1] if len(retrievers) > 1 else TavilyRetriever()
            self._tertiary = retrievers[2] if len(retrievers) > 2 else ScraperRetriever()
        else:
            self._primary, self._secondary, self._tertiary = _default_retrievers()

    async def retrieve(
        self,
        query: str,
        filters: RetrievalFilters | None = None,
    ) -> tuple[list[RetrievedChunk], str]:
        """
        Execute the retrieval cascade and return chunks + the tier that succeeded.

        Args:
            query: The search query.
            filters: Optional metadata filters from IntentPayload.

        Returns:
            Tuple of (chunks, tier_name). tier_name is one of
            'pathway', 'local', 'tavily', or 'scraper'.

        Raises:
            FallbackExhaustedError: Only if every tier fails AND produces
                                     zero chunks total.
        """
        filter_dict = filters.to_dict() if filters else None
        search_query = query

        # ── Tier 0: Primary retriever ────────────────────────────────────────
        chunks = await self._try_retriever(self._primary, search_query, filter_dict)
        if self._is_sufficient(chunks):
            logger.info("Tier 0 succeeded", tier=self._primary.tier_name, n_chunks=len(chunks))
            return chunks, self._primary.tier_name

        # ── Tier 1: Query rewrite + primary retry ────────────────────────────
        if self._rewriter is not None:
            rewritten = await self._try_rewrite(query)
            if rewritten and rewritten != query:
                search_query = rewritten
                chunks = await self._try_retriever(self._primary, search_query, filter_dict)
                if self._is_sufficient(chunks):
                    logger.info(
                        "Tier 1 succeeded",
                        tier=f"{self._primary.tier_name}_rewrite",
                        n_chunks=len(chunks),
                    )
                    return chunks, self._primary.tier_name

        # ── Tier 2: Tavily AI Search ─────────────────────────────────────────
        chunks = await self._try_retriever(self._secondary, search_query, filter_dict)
        if chunks:
            logger.info("Tier 2 succeeded", tier=self._secondary.tier_name, n_chunks=len(chunks))
            return chunks, self._secondary.tier_name

        # ── Tier 3: Web scraper ──────────────────────────────────────────────
        chunks = await self._try_retriever(self._tertiary, search_query, filter_dict)
        if chunks:
            logger.info("Tier 3 succeeded", tier="scraper", n_chunks=len(chunks))
            return chunks, self._tertiary.tier_name

        # ── All tiers exhausted ──────────────────────────────────────────────
        raise FallbackExhaustedError(
            "All retrieval tiers exhausted — no chunks retrieved",
            details={"query": query},
        )

    async def close(self) -> None:
        """Release resources held by retriever clients."""
        for retriever in (self._primary, self._secondary, self._tertiary):
            if hasattr(retriever, "close"):
                await retriever.close()

    # ── Private helpers ──────────────────────────────────────────────────────

    async def _try_retriever(
        self,
        retriever: BaseRetriever,
        query: str,
        filters: dict | None,
    ) -> list[RetrievedChunk]:
        """Attempt a single retriever, swallowing its errors."""
        try:
            return await retriever.retrieve(query, filters=filters, top_k=self._top_k)
        except RetrievalError as exc:
            logger.warning(
                "Retriever failed",
                tier=retriever.tier_name,
                error=str(exc),
            )
            return []
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Unexpected retriever error",
                tier=retriever.tier_name,
                error=str(exc),
            )
            return []

    async def _try_rewrite(self, query: str) -> str | None:
        """Attempt query rewriting, returning None on failure."""
        try:
            return await self._rewriter.rewrite(query)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Query rewrite failed", error=str(exc))
            return None

    def _is_sufficient(self, chunks: list[RetrievedChunk]) -> bool:
        """Check if retrieved chunks meet the CRAG relevance threshold."""
        if not chunks:
            return False
        # In-process local store uses keyword embeddings with lower scores.
        if self._primary.tier_name == "local":
            return True
        mean_score = sum(c.relevance_score for c in chunks) / len(chunks)
        return mean_score >= self._threshold
