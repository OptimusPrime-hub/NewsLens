"""
Tavily AI retriever (Tier-2 fallback — replaces Bing Search).

Tavily is purpose-built for AI/RAG pipelines: it returns pre-filtered,
relevance-ranked web search results as clean text snippets — no HTML parsing needed.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.m2_agents.retrieval.base import BaseRetriever
from src.m2_agents.retrieval.failure_simulation import raise_if_simulated
from src.m2_agents.schemas import RetrievedChunk
from src.shared.config import get_settings
from src.shared.exceptions import RetrievalError
from src.shared.logging import get_logger

logger = get_logger(__name__)


class TavilyRetriever(BaseRetriever):
    """Retrieves news results from Tavily AI Search API (Tier-2 fallback)."""

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.tavily_api_key

    @property
    def tier_name(self) -> str:
        return "tavily"

    async def retrieve(
        self,
        query: str,
        *,
        filters: dict | None = None,
        top_k: int = 10,
    ) -> list[RetrievedChunk]:
        """
        Search Tavily and return results as RetrievedChunk.

        Args:
            query: The search query.
            filters: Ignored (Tavily handles relevance internally).
            top_k: Number of results to request.

        Returns:
            List of RetrievedChunk from Tavily web search results.

        Raises:
            RetrievalError: If Tavily API key is missing or the call fails.
        """
        raise_if_simulated("tavily", RetrievalError)

        if not self._api_key:
            raise RetrievalError("TAVILY_API_KEY not configured")

        try:
            from tavily import TavilyClient  # type: ignore[import]
            client = TavilyClient(api_key=self._api_key)
            response = client.search(
                query=query,
                search_depth="advanced",
                topic="news",
                max_results=top_k,
                include_answer=False,
            )
        except ImportError as exc:
            raise RetrievalError("tavily-python package not installed") from exc
        except Exception as exc:
            logger.error("Tavily search failed", error=str(exc))
            raise RetrievalError(f"Tavily API error: {exc}") from exc

        return self._parse_results(response.get("results", []))

    @staticmethod
    def _parse_results(results: list[dict]) -> list[RetrievedChunk]:
        """Convert Tavily result dicts into RetrievedChunk list."""
        chunks: list[RetrievedChunk] = []
        for idx, item in enumerate(results):
            title = item.get("title", "")
            content = item.get("content", "")
            text = f"{title}\n\n{content}" if title else content
            url = item.get("url", "")
            # Tavily returns a relevance score in [0, 1]
            score = float(item.get("score", round(1.0 - idx * 0.05, 2)))

            chunks.append(
                RetrievedChunk(
                    chunk_id=f"tavily_{idx}",
                    chunk_text=text,
                    publisher=_domain_from_url(url),
                    publish_ts=datetime.now(tz=UTC),
                    relevance_score=min(score, 1.0),
                    source_url=url,
                )
            )
        return chunks


def _domain_from_url(url: str) -> str:
    """Extract bare domain name from a URL for use as publisher label."""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc
        # Strip www. prefix
        return host.removeprefix("www.") if host else "web"
    except Exception:
        return "web"
