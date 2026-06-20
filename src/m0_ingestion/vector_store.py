"""
M0 — VectorStore
Provides the VectorStore class used by main.py, plus the Pathway
VectorStoreServer setup used by the background pipeline.

VectorStore is an in-process store backed by sentence-transformers
(BAAI/bge-small-en-v1.5) with cosine similarity search.
Falls back gracefully when the local model is unavailable.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

import numpy as np
from loguru import logger

from src.shared.config import get_settings

config = get_settings()


# ---------------------------------------------------------------------------
# Simple in-process VectorStore (used by main.py)
# ---------------------------------------------------------------------------

class VectorStore:
    """
    Lightweight in-process vector store.

    Usage (matches main.py exactly):
        store = VectorStore()
        store.add_articles(articles)   # list of dicts with at least 'content'
        results = store.search(query)  # returns list of chunk text strings
    """

    def __init__(self) -> None:
        self._texts: list[str] = []
        self._meta: list[dict] = []
        self._matrix: np.ndarray | None = None   # shape (N, dim)
        self._model = None
        self._embedder_ready = False
        self._try_load_model()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _try_load_model(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # noqa
            self._model = SentenceTransformer(config.local_embedding_model)
            self._embedder_ready = True
            logger.info(f"[VectorStore] Loaded local model: {config.local_embedding_model}")
        except Exception as exc:
            logger.warning(f"[VectorStore] Could not load local embedder: {exc}. "
                           "search() will fall back to keyword matching.")

    # ------------------------------------------------------------------
    # Public API (matches main.py)
    # ------------------------------------------------------------------

    def add_articles(self, articles: list[dict[str, Any]]) -> None:
        """
        Accept a list of article dicts.
        Expects at least a 'content' or 'text' key; optionally 'title',
        'publisher', 'url', 'publish_ts'.
        """
        texts: list[str] = []
        for art in articles:
            text = art.get("content") or art.get("text") or art.get("chunk_text") or ""
            title = art.get("title", "")
            combined = f"{title}\n{text}".strip() if title else text
            if not combined:
                continue
            texts.append(combined)
            self._meta.append(art)

        if not texts:
            logger.warning("[VectorStore] add_articles called but no text content found")
            return

        self._texts.extend(texts)

        if self._embedder_ready and self._model is not None:
            new_vecs = self._model.encode(texts, convert_to_numpy=True,
                                          show_progress_bar=False).astype(np.float32)
            if self._matrix is None:
                self._matrix = new_vecs
            else:
                self._matrix = np.vstack([self._matrix, new_vecs])

        logger.info(f"[VectorStore] Added {len(texts)} articles — total: {len(self._texts)}")

    def search(self, query: str, top_k: int = 5) -> list[str]:
        """
        Return the top_k most relevant text chunks for *query*.
        Uses cosine similarity when embedder is available,
        otherwise falls back to keyword overlap scoring.
        """
        if not self._texts:
            return []

        if self._embedder_ready and self._model is not None and self._matrix is not None:
            return self._search_semantic(query, top_k)
        return self._search_keyword(query, top_k)

    # ------------------------------------------------------------------
    # Internal search implementations
    # ------------------------------------------------------------------

    def _search_semantic(self, query: str, top_k: int) -> list[str]:
        q_vec = self._model.encode([query], convert_to_numpy=True).astype(np.float32)[0]
        q_norm = q_vec / (np.linalg.norm(q_vec) + 1e-9)

        norms = np.linalg.norm(self._matrix, axis=1, keepdims=True) + 1e-9
        normed = self._matrix / norms
        scores = normed @ q_norm

        top_idx = scores.argsort()[::-1][:top_k]
        return [self._texts[i] for i in top_idx]

    def _search_keyword(self, query: str, top_k: int) -> list[str]:
        """Simple keyword overlap fallback."""
        q_words = set(query.lower().split())
        scored = []
        for i, text in enumerate(self._texts):
            t_words = set(text.lower().split())
            score = len(q_words & t_words)
            scored.append((score, i))
        scored.sort(reverse=True)
        return [self._texts[i] for _, i in scored[:top_k]]

    def __len__(self) -> int:
        return len(self._texts)


# ---------------------------------------------------------------------------
# Pathway VectorStoreServer setup (used by pipeline.py background process)
# ---------------------------------------------------------------------------

def build_vector_store_server():
    """
    Build and return a configured Pathway VectorStoreServer.
    Only called when Pathway is installed.
    """
    try:
        import pathway as pw  # noqa: F401
        from pathway.xpacks.llm.vector_store import VectorStoreServer
        from pathway.xpacks.llm.embedders import OpenAIEmbedder, SentenceTransformerEmbedder
    except ImportError as exc:
        raise RuntimeError(
            "Pathway is not installed. Run `pip install pathway`."
        ) from exc

    if config.openai_api_key:
        try:
            embedder = OpenAIEmbedder(
                model=config.embedding_model,
                api_key=config.openai_api_key,
            )
            logger.info(f"[VectorStore] Pathway using OpenAI embedder: {config.embedding_model}")
        except Exception as exc:
            logger.warning(f"[VectorStore] OpenAI embedder failed: {exc}; using local")
            embedder = SentenceTransformerEmbedder(model=config.local_embedding_model)
    else:
        embedder = SentenceTransformerEmbedder(model=config.local_embedding_model)
        logger.info(f"[VectorStore] Pathway using local embedder: {config.local_embedding_model}")

    server = VectorStoreServer(*[], embedder=embedder)
    return server, embedder


def get_vector_store_client():
    """Return a Pathway VectorStoreClient for M2 retrieval."""
    try:
        from pathway.xpacks.llm.vector_store import VectorStoreClient
    except ImportError as exc:
        raise RuntimeError("Pathway not installed.") from exc

    from pathway.xpacks.llm.vector_store import VectorStoreClient
    client = VectorStoreClient(host=config.pathway_host, port=config.pathway_port)
    logger.debug(f"[VectorStore] Client → {config.pathway_host}:{config.pathway_port}")
    return client
