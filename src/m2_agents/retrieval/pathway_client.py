"""
Pathway VectorStore retriever.

Connects to the Pathway VectorStoreServer REST endpoint and converts
raw JSON results into RetrievedChunk models.
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
from src.shared.exceptions import PathwayRetrievalError
from src.shared.logging import get_logger

logger = get_logger(__name__)


class PathwayRetriever(BaseRetriever):
    """Retrieves chunks from the Pathway VectorStoreServer."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        settings = get_settings()
        self._host = host or settings.pathway_host
        self._port = port or settings.pathway_port
        self._base_url = f"http://{self._host}:{self._port}"
        self._client = httpx.AsyncClient(timeout=30.0)

    @property
    def tier_name(self) -> str:
        return "pathway"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
        reraise=True,
    )
    async def retrieve(
        self,
        query: str,
        *,
        filters: dict | None = None,
        top_k: int = 15,
    ) -> list[RetrievedChunk]:
        """
        Query the Pathway VectorStore REST API.

        Args:
            query: Natural language search query.
            filters: Metadata filters (publishers, date_range, etc.).
            top_k: Number of results to request.

        Returns:
            List of RetrievedChunk sorted by relevance descending.

        Raises:
            PathwayRetrievalError: If Pathway is unreachable after retries.
        """
        payload = {
            "query": query,
            "k": top_k,
        }
        if filters:
            # Pathway expects a `metadata_filter` key
            payload["metadata_filter"] = self._translate_filters(filters)

        try:
            response = await self._client.post(
                f"{self._base_url}/v1/retrieve",
                json=payload,
            )
            response.raise_for_status()
            raw_results = response.json()
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as exc:
            logger.error("Pathway query failed", error=str(exc))
            raise PathwayRetrievalError(
                f"Pathway VectorStore unreachable: {exc}",
            ) from exc

        return self._parse_results(raw_results)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _translate_filters(filters: dict) -> str:
        """
        Convert our generic filter dict to Pathway's JMESPath filter string.

        Pathway VectorStoreServer accepts a JMESPath expression for filtering.
        """
        conditions: list[str] = []

        if publishers := filters.get("publishers"):
            pub_list = " || ".join(
                f"publisher == '{p}'" for p in publishers
            )
            conditions.append(f"({pub_list})")

        if date_start := filters.get("date_start"):
            conditions.append(f"publish_ts >= '{date_start}'")

        if date_end := filters.get("date_end"):
            conditions.append(f"publish_ts <= '{date_end}'")

        return " && ".join(conditions) if conditions else ""

    @staticmethod
    def _parse_results(raw: list[dict] | dict) -> list[RetrievedChunk]:
        """Convert Pathway JSON response into typed chunks."""
        # Pathway may return a list or a dict with a 'results' key
        items = raw if isinstance(raw, list) else raw.get("results", [])

        chunks: list[RetrievedChunk] = []
        for item in items:
            try:
                chunk = RetrievedChunk(
                    chunk_id=str(item.get("id", item.get("chunk_id", ""))),
                    chunk_text=item.get("text", item.get("chunk_text", "")),
                    publisher=item.get("metadata", {}).get("publisher", "unknown"),
                    publish_ts=datetime.fromisoformat(
                        item.get("metadata", {}).get(
                            "publish_ts",
                            datetime.now(tz=UTC).isoformat(),
                        ),
                    ),
                    relevance_score=float(item.get("score", item.get("dist", 0.0))),
                )
                chunks.append(chunk)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning("Skipping malformed Pathway result", error=str(exc))
                continue

        return sorted(chunks, key=lambda c: c.relevance_score, reverse=True)
