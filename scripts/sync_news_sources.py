"""Continuously sync live news into the folder watched by Pathway."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.m0_ingestion.connectors.newsapi_connector import NewsAPIConnector
from src.m0_ingestion.connectors.rss_connector import RSSConnector
from src.m0_ingestion.schemas import RawArticle
from src.shared.config import get_settings
from src.shared.logging import get_logger

logger = get_logger(__name__)


def _source_dir() -> Path:
    glob_path = get_settings().pathway_source_glob
    if "*" in glob_path:
        return Path(glob_path.split("*", 1)[0]).resolve()
    return Path(glob_path).resolve().parent


def _article_id(article: RawArticle) -> str:
    return hashlib.sha1(article.url.encode("utf-8")).hexdigest()[:16]


def _write_articles(target: Path, articles: list[RawArticle]) -> int:
    target.mkdir(parents=True, exist_ok=True)
    written = 0
    for article in articles:
        path = target / f"{_article_id(article)}.json"
        if path.exists():
            continue
        path.write_text(article.model_dump_json(), encoding="utf-8")
        written += 1
    return written


def main() -> None:
    settings = get_settings()
    target = _source_dir()
    newsapi = NewsAPIConnector()
    rss = RSSConnector()

    logger.info("Starting news sync", target=str(target), query=settings.news_sync_query)
    while True:
        try:
            articles = newsapi.fetch(settings.news_sync_query) + rss.fetch_all()
            written = _write_articles(target, articles)
            logger.info("News sync completed", fetched=len(articles), written=written)
        except Exception as exc:  # noqa: BLE001
            logger.exception("News sync failed", error=str(exc))
        time.sleep(settings.pathway_refresh_interval_ms / 1000)


if __name__ == "__main__":
    main()
