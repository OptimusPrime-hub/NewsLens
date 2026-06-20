"""
M0 — NewsAPI Connector
Polls NewsAPI.ai for fresh articles and emits RawArticle rows into the
Pathway pipeline. Runs as a pw.io.python.read() input source.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
from loguru import logger

from src.m0_ingestion.schemas import RawArticle
from src.shared.config import get_config

config = get_config()


class NewsAPIConnector:
    """
    Wraps NewsAPI.ai (newsapi.org v2 compatible) HTTP polling.
    Call `.stream(subject, callback)` to start emitting RawArticle objects.
    """

    BASE_URL = "https://newsapi.org/v2/everything"

    def __init__(self) -> None:
        self.api_key = config.newsapi_key
        self.refresh_interval_ms = config.pathway_refresh_interval_ms
        self._seen_urls: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, query: str, page_size: int = 20) -> list[RawArticle]:
        """
        Fetch the latest articles for *query* from NewsAPI.
        Returns a list of RawArticle — de-duped against already-seen URLs.
        """
        params = {
            "q": query,
            "pageSize": page_size,
            "sortBy": "publishedAt",
            "language": "en",
            "apiKey": self.api_key,
        }

        try:
            response = httpx.get(self.BASE_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(f"[NewsAPI] HTTP error: {exc.response.status_code} — {exc}")
            return []
        except Exception as exc:
            logger.error(f"[NewsAPI] Unexpected error: {exc}")
            return []

        articles: list[RawArticle] = []
        for item in data.get("articles", []):
            url = item.get("url", "")
            if not url or url in self._seen_urls:
                continue

            content = item.get("content") or item.get("description") or ""
            if not content.strip():
                continue

            try:
                publish_ts = datetime.fromisoformat(
                    item.get("publishedAt", "").replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                publish_ts = datetime.now(UTC)

            articles.append(
                RawArticle(
                    url=url,
                    title=item.get("title") or "",
                    content=content,
                    publish_ts=publish_ts,
                    source_name=item.get("source", {}).get("name") or "unknown",
                )
            )
            self._seen_urls.add(url)

        logger.info(f"[NewsAPI] Fetched {len(articles)} new articles for query='{query}'")
        return articles

    def stream(
        self,
        query: str,
        callback: Callable[[RawArticle], None],
        max_polls: int | None = None,
    ) -> None:
        """
        Blocking poll loop — calls *callback* for each new RawArticle.
        Sleeps `refresh_interval_ms` between polls.
        Set max_polls for testing; None = run forever.
        """
        poll_count = 0
        while max_polls is None or poll_count < max_polls:
            for article in self.fetch(query):
                callback(article)
            poll_count += 1
            if max_polls is None or poll_count < max_polls:
                time.sleep(self.refresh_interval_ms / 1000)


def build_pathway_subject_fetcher(query: str = "world news") -> Callable[[], list[dict]]:
    """
    Factory that returns a zero-argument callable suitable for
    pw.io.python.read(). Each call returns a list of dicts representing
    new RawArticle records.
    """
    connector = NewsAPIConnector()

    def fetch() -> list[dict]:
        articles = connector.fetch(query)
        return [a.model_dump(mode="json") for a in articles]

    return fetch
