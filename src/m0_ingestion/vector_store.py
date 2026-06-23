"""Vector-store helpers for CLI search and the Pathway index service."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
from loguru import logger

from src.m0_ingestion.processors.embedder import Embedder
from src.shared.config import get_settings

config = get_settings()


class VectorStore:
    """Small in-process vector store used only by the CLI smoke path."""

    def __init__(self) -> None:
        self._texts: list[str] = []
        self._meta: list[dict] = []
        self._matrix: np.ndarray | None = None
        self._embedder = Embedder()

    def add_articles(self, articles: list[dict[str, Any]]) -> None:
        """Add article dictionaries with content/text/chunk_text fields."""
        texts: list[str] = []
        for article in articles:
            text = article.get("content") or article.get("text") or article.get("chunk_text") or ""
            title = article.get("title", "")
            combined = f"{title}\n{text}".strip() if title else text
            if not combined:
                continue
            texts.append(combined)
            self._meta.append(article)

        if not texts:
            logger.warning("[VectorStore] add_articles called with no text")
            return

        self._texts.extend(texts)
        new_vecs = self._embedder.embed_texts(texts).astype(np.float32)
        self._matrix = new_vecs if self._matrix is None else np.vstack([self._matrix, new_vecs])
        logger.info(f"[VectorStore] Added {len(texts)} articles; total={len(self._texts)}")

    def search(self, query: str, top_k: int = 5) -> list[str]:
        """Return top-k matching text chunks."""
        if not self._texts:
            return []
        if self._matrix is None:
            return self._search_keyword(query, top_k)
        return self._search_semantic(query, top_k)

    def _search_semantic(self, query: str, top_k: int) -> list[str]:
        q_vec = self._embedder.embed_texts([query]).astype(np.float32)[0]
        q_norm = q_vec / (np.linalg.norm(q_vec) + 1e-9)
        norms = np.linalg.norm(self._matrix, axis=1, keepdims=True) + 1e-9
        scores = (self._matrix / norms) @ q_norm
        top_idx = scores.argsort()[::-1][:top_k]
        return [self._texts[i] for i in top_idx]

    def _search_keyword(self, query: str, top_k: int) -> list[str]:
        q_words = set(query.lower().split())
        scored = []
        for index, text in enumerate(self._texts):
            score = len(q_words & set(text.lower().split()))
            scored.append((score, index))
        scored.sort(reverse=True)
        return [self._texts[index] for _, index in scored[:top_k]]

    def __len__(self) -> int:
        return len(self._texts)


def parse_article_json(raw: bytes) -> list[tuple[str, dict[str, str]]]:
    """Parse one JSON article file into Pathway text + metadata pairs."""
    item = json.loads(raw.decode("utf-8"))
    title = str(item.get("title") or "")
    content = str(item.get("content") or "")
    text = f"{title}\n\n{content}".strip()
    if not text:
        return []

    metadata = {
        "publisher": str(item.get("source_name") or item.get("publisher") or "unknown"),
        "url": str(item.get("url") or ""),
        "publish_ts": str(item.get("publish_ts") or ""),
        "title": title,
    }
    return [(text, metadata)]


def build_pathway_vector_server():
    """Build a Pathway VectorStoreServer over the shared article JSON folder."""
    import pathway as pw
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from pathway.xpacks.llm.vector_store import VectorStoreServer

    docs = pw.io.fs.read(
        path=config.pathway_source_glob,
        format="binary",
        with_metadata=True,
    )
    embedder = GoogleGenerativeAIEmbeddings(
        model=config.gemini_embedding_model,
        google_api_key=config.gemini_api_key,
    )
    return VectorStoreServer.from_langchain_components(
        docs,
        embedder=embedder,
        parser=parse_article_json,
    )
