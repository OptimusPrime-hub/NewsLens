"""
Contract tests to ensure Module 0 ingestion schemas remain compatible across packages.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json

from src.m0_ingestion.schemas import ArticleChunk, NormalizedArticle, RawArticle


def test_m0_ingestion_contracts():
    """Verify RawArticle, NormalizedArticle, and ArticleChunk contracts."""
    raw = RawArticle(
        url="http://example.com/news",
        title="Test Title",
        content="Raw body content.",
        publish_ts=datetime.now(tz=timezone.utc),
        source_name="Example News",
    )
    
    # Serialize raw
    raw_json = raw.model_dump_json()
    validated_raw = RawArticle.model_validate_json(raw_json)
    assert validated_raw.url == raw.url
    assert validated_raw.source_name == "Example News"

    normalized = NormalizedArticle(
        article_id="hash123",
        title="Normalized Title",
        text="Cleaned body text.",
        publisher="Example",
        publish_ts=datetime.now(tz=timezone.utc),
        url="http://example.com/news",
    )

    # Serialize normalized
    norm_json = normalized.model_dump_json()
    validated_norm = NormalizedArticle.model_validate_json(norm_json)
    assert validated_norm.article_id == "hash123"
    assert validated_norm.publisher == "Example"

    chunk = ArticleChunk(
        chunk_id="chunk_0",
        article_id="hash123",
        chunk_text="A single segment of text.",
        publisher="Example",
        publish_ts=datetime.now(tz=timezone.utc),
        url="http://example.com/news",
    )

    # Serialize chunk
    chunk_json = chunk.model_dump_json()
    validated_chunk = ArticleChunk.model_validate_json(chunk_json)
    assert validated_chunk.chunk_id == "chunk_0"
    assert validated_chunk.publisher == "Example"
