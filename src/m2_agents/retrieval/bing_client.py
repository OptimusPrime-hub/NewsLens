"""
Bing Search API v7 retriever (Tier-2 fallback).

Converts web search results into RetrievedChunk format so they're
indistinguishable from Pathway results downstream.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.m2_agents.retrieval.base import BaseRetriever
from src.m2_agents.schemas import RetrievedChunk
from src.shared.config import get_settings
from src.shared.exceptions import BingRetrievalError
from src.shared.logging import get_logger

logger = get_logger(__name__)


class BingRetriever(BaseRetriever):
    """Retrieves news results from Bing Search API v7."""

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.bing_api_key
        self._endpoint = settings.bing_endpoint
        self._client = httpx.AsyncClient(timeout=15.0)

    @property
    def tier_name(self) -> str:
        return "bing"

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        reraise=True,
    )
    async def retrieve(
        self,
        query: str,
        *,
        filters: dict | None = None,
        top_k: int = 10,
    ) -> list[RetrievedChunk]:
        """
        Search Bing and return results as RetrievedChunk.

        Args:
            query: The search query.
            filters: Ignored for Bing (web search doesn't support metadata filters).
            top_k: Number of results to request.

        Returns:
            List of RetrievedChunk from web search results.

        Raises:
            BingRetrievalError: If Bing API key is missing or the call fails.
        """
        if not self._api_key:
            raise BingRetrievalError("BING_API_KEY not configured")

        headers = {"Ocp-Apim-Subscription-Key": self._api_key}
        params = {
            "q": query,
            "count": str(top_k),
            "responseFilter": "Webpages",
            "freshness": "Week",  # prefer recent news
        }

        try:
            response = await self._client.get(
                self._endpoint,
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPStatusError, httpx.ConnectError) as exc:
            logger.error("Bing Search failed", error=str(exc))
            raise BingRetrievalError(f"Bing API error: {exc}") from exc

        return self._parse_results(data)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    @staticmethod
    def _parse_results(data: dict) -> list[RetrievedChunk]:
        """Convert Bing JSON response into RetrievedChunk list."""
        pages = data.get("webPages", {}).get("value", [])
        chunks: list[RetrievedChunk] = []

        for idx, page in enumerate(pages):
            snippet = page.get("snippet", "")
            name = page.get("name", "")
            text = f"{name}\n\n{snippet}" if name else snippet

            chunks.append(
                RetrievedChunk(
                    chunk_id=f"bing_{idx}",
                    chunk_text=text,
                    publisher=page.get("displayUrl", "web").split("/")[0],
                    publish_ts=_parse_bing_date(page.get("dateLastCrawled")),
                    relevance_score=round(1.0 - (idx * 0.05), 2),  # rank-based score
                    source_url=page.get("url", ""),
                ),
            )

        return chunks


def _parse_bing_date(date_str: str | None) -> datetime:
    """Parse Bing's date format, falling back to now."""
    if date_str:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    return datetime.now(tz=UTC)
