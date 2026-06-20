"""
Abstract base class for all retrieval backends.

Every retriever (Pathway, Bing, Scraper) implements this interface,
so RetrievalManager can orchestrate without knowing implementation details.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.m2_agents.schemas import RetrievedChunk


class BaseRetriever(ABC):
    """Protocol that every retrieval backend must satisfy."""

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        *,
        filters: dict | None = None,
        top_k: int = 15,
    ) -> list[RetrievedChunk]:
        """
        Fetch relevant document chunks for the given query.

        Args:
            query: The search query string.
            filters: Optional metadata filters (publisher, date_range, etc.).
            top_k: Maximum number of chunks to return.

        Returns:
            A list of RetrievedChunk, each with a relevance_score.
        """

    @property
    @abstractmethod
    def tier_name(self) -> str:
        """Human-readable tier identifier (e.g. 'pathway', 'bing', 'scraper')."""
