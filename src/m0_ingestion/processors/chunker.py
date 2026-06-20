"""
M0 — Semantic Chunker
Splits NormalizedArticle text into 512-token chunks with 64-token overlap,
producing ArticleChunk records ready for embedding.

Token counting uses a simple whitespace approximation (≈ 0.75 words/token)
to avoid importing a full tokenizer in the ingestion hot path. For
production-grade accuracy swap `_approx_tokens` for tiktoken.
"""

from __future__ import annotations

import hashlib
import re

from loguru import logger

from src.m0_ingestion.schemas import ArticleChunk, NormalizedArticle

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CHUNK_TOKEN_SIZE = 512   # target chunk size in tokens
OVERLAP_TOKENS   = 64    # overlap between consecutive chunks
WORDS_PER_TOKEN  = 0.75  # approximation factor


def _approx_tokens(text: str) -> int:
    """Rough token count via word count heuristic."""
    return int(len(text.split()) / WORDS_PER_TOKEN)


def _chunk_id(article_id: str, idx: int) -> str:
    raw = f"{article_id}::{idx}"
    return hashlib.sha1(raw.encode()).hexdigest()[:20]


def _split_sentences(text: str) -> list[str]:
    """Split text on sentence boundaries while keeping the delimiter."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------

class SemanticChunker:
    """
    Sentence-aware sliding-window chunker.

    Strategy:
    1. Split article text into sentences.
    2. Greedily accumulate sentences until the approximate token budget is
       reached (CHUNK_TOKEN_SIZE).
    3. Back-track OVERLAP_TOKENS worth of text for the next window.
    4. Emit an ArticleChunk per window.
    """

    def __init__(
        self,
        chunk_tokens: int = CHUNK_TOKEN_SIZE,
        overlap_tokens: int = OVERLAP_TOKENS,
    ) -> None:
        self.chunk_tokens   = chunk_tokens
        self.overlap_tokens = overlap_tokens

    # ------------------------------------------------------------------
    def chunk(self, article: NormalizedArticle) -> list[ArticleChunk]:
        sentences = _split_sentences(article.text)
        if not sentences:
            return []

        chunks: list[ArticleChunk] = []
        current_sentences: list[str] = []
        current_tokens = 0
        idx = 0

        for sentence in sentences:
            sent_tokens = _approx_tokens(sentence)

            # If adding this sentence exceeds budget → emit a chunk
            if current_tokens + sent_tokens > self.chunk_tokens and current_sentences:
                chunk_text = " ".join(current_sentences)
                chunks.append(
                    ArticleChunk(
                        chunk_id=_chunk_id(article.article_id, idx),
                        article_id=article.article_id,
                        chunk_text=chunk_text,
                        publisher=article.publisher,
                        publish_ts=article.publish_ts,
                        url=article.url,
                    )
                )
                idx += 1

                # Build overlap window — keep trailing sentences that fit
                overlap_sentences: list[str] = []
                overlap_tok = 0
                for s in reversed(current_sentences):
                    t = _approx_tokens(s)
                    if overlap_tok + t > self.overlap_tokens:
                        break
                    overlap_sentences.insert(0, s)
                    overlap_tok += t

                current_sentences = overlap_sentences
                current_tokens = overlap_tok

            current_sentences.append(sentence)
            current_tokens += sent_tokens

        # Flush remaining sentences
        if current_sentences:
            chunk_text = " ".join(current_sentences)
            if _approx_tokens(chunk_text) > 10:  # skip tiny tail fragments
                chunks.append(
                    ArticleChunk(
                        chunk_id=_chunk_id(article.article_id, idx),
                        article_id=article.article_id,
                        chunk_text=chunk_text,
                        publisher=article.publisher,
                        publish_ts=article.publish_ts,
                        url=article.url,
                    )
                )

        logger.debug(
            f"[Chunker] {article.article_id} → {len(chunks)} chunks "
            f"(~{_approx_tokens(article.text)} tokens total)"
        )
        return chunks

    def chunk_batch(self, articles: list[NormalizedArticle]) -> list[ArticleChunk]:
        all_chunks: list[ArticleChunk] = []
        for article in articles:
            all_chunks.extend(self.chunk(article))
        logger.info(f"[Chunker] {len(all_chunks)} chunks from {len(articles)} articles")
        return all_chunks
