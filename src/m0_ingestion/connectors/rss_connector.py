"""
M0 — RSS Feed Connector
Polls a curated list of RSS feeds for major news outlets.
Serves as the secondary live-news source and Tier-1 fallback when
NewsAPI.ai is rate-limited or unavailable.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable

import feedparser
from loguru import logger

from src.shared.config import get_config
from src.m0_ingestion.schemas import RawArticle

config = get_config()

# ---------------------------------------------------------------------------
# Curated feed list — add / remove as needed
# ---------------------------------------------------------------------------
DEFAULT_FEEDS: list[tuple[str, str]] = [
    ("Reuters", "https://feeds.reuters.com/reuters/topNews"),
    ("BBC News", "https://feeds.bbci.co.uk/news/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("NPR", "https://feeds.npr.org/1001/rss.xml"),
    ("Associated Press", "https://rsshub.app/apnews/topics/apf-topnews"),
    ("The Guardian", "https://www.theguardian.com/world/rss"),
    ("Fox News", "https://moxie.foxnews.com/google-publisher/world.xml"),
    ("CNN", "http://rss.cnn.com/rss/edition_world.rss"),
    ("NYT", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
    ("Washington Post", "https://feeds.washingtonpost.com/rss/world"),
]


def _parse_date(entry: feedparser.FeedParserDict) -> datetime:
    """Best-effort publish timestamp extraction from a feedparser entry."""
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw).astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                pass
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _url_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


class RSSConnector:
    """
    Polls a list of RSS feed URLs and emits new RawArticle objects.
    """

    def __init__(self, feeds: list[tuple[str, str]] | None = None) -> None:
        self.feeds = feeds or DEFAULT_FEEDS
        self.refresh_interval_ms = config.pathway_rss_refresh_interval_ms
        self._seen_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_all(self) -> list[RawArticle]:
        """Fetch new articles from all configured RSS feeds."""
        articles: list[RawArticle] = []
        for source_name, feed_url in self.feeds:
            articles.extend(self._fetch_feed(source_name, feed_url))
        logger.info(f"[RSS] Fetched {len(articles)} new articles across {len(self.feeds)} feeds")
        return articles

    def _fetch_feed(self, source_name: str, feed_url: str) -> list[RawArticle]:
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as exc:
            logger.warning(f"[RSS] Failed to parse {feed_url}: {exc}")
            return []

        articles: list[RawArticle] = []
        for entry in parsed.entries:
            url = getattr(entry, "link", "") or ""
            if not url:
                continue

            uid = _url_id(url)
            if uid in self._seen_ids:
                continue

            content = (
                getattr(entry, "summary", "")
                or getattr(entry, "description", "")
                or ""
            )
            title = getattr(entry, "title", "") or ""

            if not content.strip() and not title.strip():
                continue

            articles.append(
                RawArticle(
                    url=url,
                    title=title,
                    content=content,
                    publish_ts=_parse_date(entry),
                    source_name=source_name,
                )
            )
            self._seen_ids.add(uid)

        return articles

    def stream(
        self,
        callback: Callable[[RawArticle], None],
        max_polls: int | None = None,
    ) -> None:
        """
        Blocking poll loop that calls *callback* for each new RawArticle.
        Sleeps `rss_refresh_interval_ms` between full-sweep polls.
        """
        poll_count = 0
        while max_polls is None or poll_count < max_polls:
            for article in self.fetch_all():
                callback(article)
            poll_count += 1
            if max_polls is None or poll_count < max_polls:
                time.sleep(self.refresh_interval_ms / 1000)


def build_pathway_rss_fetcher() -> Callable[[], list[dict]]:
    """
    Factory returning a zero-argument callable for pw.io.python.read().
    """
    connector = RSSConnector()

    def fetch() -> list[dict]:
        articles = connector.fetch_all()
        return [a.model_dump(mode="json") for a in articles]

    return fetch