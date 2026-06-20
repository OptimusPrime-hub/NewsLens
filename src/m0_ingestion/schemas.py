"""
Schemas and data contracts for Module 0 (Live News Ingestion).
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class RawArticle(BaseModel):
    """Raw article schema directly from feed/API connectors."""

    url: str
    title: str
    content: str
    publish_ts: datetime
    source_name: str


class NormalizedArticle(BaseModel):
    """Cleaned, de-duplicated, and publisher-normalized article."""

    article_id: str
    title: str
    text: str
    publisher: str
    publish_ts: datetime
    url: str


class ArticleChunk(BaseModel):
    """Semantically split chunk from a normalized article."""

    chunk_id: str
    article_id: str
    chunk_text: str
    publisher: str
    publish_ts: datetime
    url: str
