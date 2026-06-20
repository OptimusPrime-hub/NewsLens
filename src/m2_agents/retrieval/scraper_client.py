"""
Web scraper retriever (Tier-3 fallback).

Uses httpx + BeautifulSoup for lightweight HTML extraction.
This is the last-resort retrieval path — no external API dependency.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from src.m2_agents.retrieval.base import BaseRetriever
from src.m2_agents.schemas import RetrievedChunk
from src.shared.exceptions import ScraperRetrievalError
from src.shared.logging import get_logger

logger = get_logger(__name__)

# Max characters to keep from a scraped page before chunking
_MAX_PAGE_CHARS = 8_000
_CHUNK_SIZE = 1_500  # ~375 tokens per chunk


class ScraperRetriever(BaseRetriever):
    """Scrapes URLs and converts page text into RetrievedChunk format."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; NewsLens/1.0; "
                    "+https://github.com/newslens)"
                ),
            },
        )

    @property
    def tier_name(self) -> str:
        return "scraper"

    async def retrieve(
        self,
        query: str,
        *,
        filters: dict | None = None,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """
        Scrape top search result URLs and chunk their text content.

        For MVP, uses a simple Google News RSS approach to find URLs.
        Then scrapes each URL and chunks the text.

        Args:
            query: The search query (used to find URLs).
            filters: Ignored for scraping.
            top_k: Max number of URLs to scrape.

        Returns:
            List of RetrievedChunk from scraped content.

        Raises:
            ScraperRetrievalError: If all scraping attempts fail.
        """
        urls = await self._find_urls(query, count=top_k)
        if not urls:
            raise ScraperRetrievalError("No URLs found to scrape")

        all_chunks: list[RetrievedChunk] = []
        for url in urls:
            try:
                chunks = await self._scrape_url(url)
                all_chunks.extend(chunks)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to scrape URL", url=url, error=str(exc))
                continue

        if not all_chunks:
            raise ScraperRetrievalError("All scraping attempts returned no content")

        return all_chunks[:top_k * 3]  # cap total chunks

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ── Private helpers ──────────────────────────────────────────────────────

    async def _find_urls(self, query: str, count: int = 5) -> list[str]:
        """
        Find news article URLs for the query.

        Uses Google News RSS as a zero-auth URL discovery method.
        """
        rss_url = (
            f"https://news.google.com/rss/search?q={httpx.QueryParams({'q': query})}"
            f"&hl=en-US&gl=US&ceid=US:en"
        )
        try:
            response = await self._client.get(rss_url)
            response.raise_for_status()
            # Simple XML link extraction (no lxml dependency required)
            text = response.text
            urls: list[str] = []
            for segment in text.split("<link>")[1:]:
                link = segment.split("</link>")[0].strip()
                if link.startswith("http") and "google.com" not in link:
                    urls.append(link)
                if len(urls) >= count:
                    break
            return urls
        except Exception as exc:  # noqa: BLE001
            logger.warning("Google News RSS failed", error=str(exc))
            return []

    async def _scrape_url(self, url: str) -> list[RetrievedChunk]:
        """Fetch a URL, extract text, and chunk it."""
        response = await self._client.get(url)
        response.raise_for_status()

        text = self._extract_text(response.text)
        if len(text) < 100:  # too short to be useful
            return []

        return self._chunk_text(text, source_url=url)

    @staticmethod
    def _extract_text(html: str) -> str:
        """
        Extract readable text from HTML using BeautifulSoup.

        Falls back to naive tag stripping if bs4 is unavailable.
        """
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")

            # Remove script, style, nav, footer
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)
        except ImportError:
            # Fallback: naive regex-based tag stripping
            import re

            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()

        return text[:_MAX_PAGE_CHARS]

    @staticmethod
    def _chunk_text(text: str, source_url: str) -> list[RetrievedChunk]:
        """Split text into fixed-size chunks with overlap."""
        chunks: list[RetrievedChunk] = []
        overlap = 200

        for i, start in enumerate(range(0, len(text), _CHUNK_SIZE - overlap)):
            chunk_text = text[start : start + _CHUNK_SIZE]
            if len(chunk_text) < 50:
                continue

            # Extract domain as publisher
            publisher = "web"
            try:
                from urllib.parse import urlparse

                publisher = urlparse(source_url).netloc
            except Exception:  # noqa: BLE001
                pass

            chunks.append(
                RetrievedChunk(
                    chunk_id=f"scraper_{publisher}_{i}",
                    chunk_text=chunk_text,
                    publisher=publisher,
                    publish_ts=datetime.now(tz=UTC),
                    relevance_score=round(0.5 - (i * 0.02), 2),  # lower baseline
                ),
            )

        return chunks
