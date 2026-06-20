"""
M0 — Article Normalizer
Strips HTML, deduplicates by URL fingerprint, and maps raw source names
to canonical publisher identifiers.
"""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser

from loguru import logger

from src.m0_ingestion.schemas import NormalizedArticle, RawArticle

# ---------------------------------------------------------------------------
# Canonical publisher name map
# Keeps publisher identity consistent across RSS, NewsAPI, and scraped pages.
# ---------------------------------------------------------------------------
PUBLISHER_ALIASES: dict[str, str] = {
    # Reuters variants
    "reuters": "reuters",
    "reuters.com": "reuters",
    "thomsonreuters": "reuters",
    # BBC
    "bbc": "bbc",
    "bbc news": "bbc",
    "bbc.co.uk": "bbc",
    "bbc.com": "bbc",
    # Al Jazeera
    "al jazeera": "aljazeera",
    "aljazeera": "aljazeera",
    "aljazeera.com": "aljazeera",
    # Fox News
    "fox news": "foxnews",
    "foxnews": "foxnews",
    "fox": "foxnews",
    # CNN
    "cnn": "cnn",
    "cnn.com": "cnn",
    # NPR
    "npr": "npr",
    "npr.org": "npr",
    "national public radio": "npr",
    # Associated Press
    "ap": "ap",
    "associated press": "ap",
    "apnews.com": "ap",
    # The Guardian
    "the guardian": "guardian",
    "guardian": "guardian",
    "theguardian.com": "guardian",
    # NYT
    "the new york times": "nyt",
    "nyt": "nyt",
    "new york times": "nyt",
    "nytimes.com": "nyt",
    # Washington Post
    "the washington post": "washingtonpost",
    "washington post": "washingtonpost",
    "washingtonpost.com": "washingtonpost",
}


def normalize_publisher(raw: str) -> str:
    """Return a canonical lowercase publisher slug, or cleaned raw name."""
    key = raw.strip().lower()
    return PUBLISHER_ALIASES.get(key, key.replace(" ", "").replace(".", ""))


# ---------------------------------------------------------------------------
# HTML stripping
# ---------------------------------------------------------------------------

class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def strip_html(html: str) -> str:
    """Strip all HTML tags and return plain text."""
    stripper = _HTMLStripper()
    try:
        stripper.feed(html)
        text = stripper.get_text()
    except Exception:
        # Fallback: crude regex strip
        text = re.sub(r"<[^>]+>", " ", html)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Deduplication helper
# ---------------------------------------------------------------------------

def _url_fingerprint(url: str) -> str:
    """Stable 20-char hex fingerprint of a URL."""
    return hashlib.sha1(url.encode()).hexdigest()[:20]


# ---------------------------------------------------------------------------
# Normalizer class
# ---------------------------------------------------------------------------

class ArticleNormalizer:
    """
    Converts RawArticle → NormalizedArticle.
    Maintains a seen-fingerprint set to drop duplicates within a session.
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def normalize(self, raw: RawArticle) -> NormalizedArticle | None:
        """
        Return a NormalizedArticle or None if the article is a duplicate
        or has insufficient content after cleaning.
        """
        fingerprint = _url_fingerprint(raw.url)
        if fingerprint in self._seen:
            logger.debug(f"[Normalizer] Duplicate skipped: {raw.url}")
            return None

        clean_text = strip_html(raw.content)
        clean_title = strip_html(raw.title)

        if len(clean_text) < 80:
            logger.debug(f"[Normalizer] Skipping too-short article: {raw.url}")
            return None

        publisher = normalize_publisher(raw.source_name)
        self._seen.add(fingerprint)

        article = NormalizedArticle(
            article_id=fingerprint,
            title=clean_title,
            text=clean_text,
            publisher=publisher,
            publish_ts=raw.publish_ts,
            url=raw.url,
        )
        logger.debug(f"[Normalizer] OK → {publisher} | {clean_title[:60]}")
        return article

    def normalize_batch(self, raws: list[RawArticle]) -> list[NormalizedArticle]:
        """Normalize a batch, skipping duplicates and low-quality articles."""
        results = [self.normalize(r) for r in raws]
        good = [a for a in results if a is not None]
        logger.info(f"[Normalizer] {len(good)}/{len(raws)} articles passed normalization")
        return good
