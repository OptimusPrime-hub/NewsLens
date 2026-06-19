"""
Retrieval orchestrator with 3-tier fallback cascade.

RetrievalManager owns ONLY the orchestration logic:
  Tier 0: Pathway VectorStore (primary)
  Tier 1: Query rewrite + Pathway retry
  Tier 2: Bing Search API
  Tier 3: Web scraper

It does NOT fetch, parse, chunk, or retry internally — each
BaseRetriever implementation handles its own concerns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.m2_agents.retrieval.base import BaseRetriever
from src.m2_agents.retrieval.bing_client import BingRetriever
from src.m2_agents.retrieval.pathway_client import PathwayRetriever
from src.m2_agents.retrieval.scraper_client import ScraperRetriever
from src.m2_agents.schemas import RetrievedChunk
from src.shared.config import get_settings
from src.shared.exceptions import FallbackExhaustedError, RetrievalError
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.m2_agents.crag.rewriter import QueryRewriter
    from src.m2_agents.retrieval.filters import RetrievalFilters

logger = get_logger(__name__)


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
            self._secondary = retrievers[1] if len(retrievers) > 1 else BingRetriever()
            self._tertiary = retrievers[2] if len(retrievers) > 2 else ScraperRetriever()
        else:
            self._primary = PathwayRetriever()
            self._secondary = BingRetriever()
            self._tertiary = ScraperRetriever()

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
            'pathway', 'bing', 'scraper', or 'partial'.

        Raises:
            FallbackExhaustedError: Only if every tier fails AND produces
                                     zero chunks total.
        """
        filter_dict = filters.to_dict() if filters else None

        # ── Tier 0: Primary retriever (Pathway) ─────────────────────────────
        chunks = await self._try_retriever(self._primary, query, filter_dict)
        if self._is_sufficient(chunks):
            logger.info("Tier 0 succeeded", tier="pathway", n_chunks=len(chunks))
            return chunks, self._primary.tier_name

        # ── Tier 1: Query rewrite + primary retry ────────────────────────────
        if self._rewriter is not None:
            rewritten = await self._try_rewrite(query)
            if rewritten and rewritten != query:
                chunks = await self._try_retriever(self._primary, rewritten, filter_dict)
                if self._is_sufficient(chunks):
                    logger.info("Tier 1 succeeded", tier="pathway_rewrite", n_chunks=len(chunks))
                    return chunks, self._primary.tier_name

        # ── Tier 2: Bing Search ──────────────────────────────────────────────
        chunks = await self._try_retriever(self._secondary, query, filter_dict)
        if chunks:
            logger.info("Tier 2 succeeded", tier="bing", n_chunks=len(chunks))
            return chunks, self._secondary.tier_name

        # ── Tier 3: Web scraper ──────────────────────────────────────────────
        chunks = await self._try_retriever(self._tertiary, query, filter_dict)
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
        mean_score = sum(c.relevance_score for c in chunks) / len(chunks)
        return mean_score >= self._threshold
