"""
M0 — Embedder
Converts ArticleChunk text into dense vector embeddings.

Primary:  Google Gemini text-embedding-004 (768-dim, cloud)
Fallback: Simple TF-IDF-like keyword vector (offline, no ML deps)

The fallback activates automatically when GEMINI_API_KEY is absent
so the pipeline continues without human intervention.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from loguru import logger

from src.m0_ingestion.schemas import ArticleChunk
from src.shared.config import get_config

config = get_config()

EmbeddingBackend = Literal["gemini", "keyword"]


class Embedder:
    """
    Embed texts using Gemini cloud embeddings or fall back to keyword hashing.
    All methods return numpy float32 arrays of shape (N, dim).
    """

    def __init__(self) -> None:
        self._backend: EmbeddingBackend = "gemini" if config.gemini_api_keys else "keyword"

    # ------------------------------------------------------------------
    # Lazy initialisation
    # ------------------------------------------------------------------

    def _get_gemini(self, api_key: str | None = None):
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        key = api_key or config.gemini_api_keys[0]
        return GoogleGenerativeAIEmbeddings(
            model=config.gemini_embedding_model,
            google_api_key=key,
        )

    # ------------------------------------------------------------------
    # Core embedding methods
    # ------------------------------------------------------------------

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """
        Embed a list of strings. Returns float32 ndarray (N, dim).
        Tries Gemini cloud first; silently switches to keyword on any error.
        """
        if not texts:
            return np.empty((0, self.embedding_dim), dtype=np.float32)

        if self._backend == "gemini" and config.gemini_api_keys:
            for index, api_key in enumerate(config.gemini_api_keys):
                try:
                    return self._embed_gemini(texts, api_key=api_key)
                except Exception as exc:
                    label = "primary" if index == 0 else "fallback"
                    logger.warning(f"[Embedder] Gemini {label} key failed ({exc})")
            logger.warning("[Embedder] All Gemini keys failed; switching to keyword fallback")
            self._backend = "keyword"

        return self._embed_keyword(texts)

    def _embed_gemini(self, texts: list[str], *, api_key: str) -> np.ndarray:
        client = self._get_gemini(api_key)
        vecs = client.embed_documents(texts)
        arr = np.array(vecs, dtype=np.float32)
        logger.debug(f"[Embedder:Gemini] Embedded {len(texts)} texts → shape {arr.shape}")
        return arr

    def _embed_keyword(self, texts: list[str]) -> np.ndarray:
        """
        Simple hash-based keyword embedding fallback.
        Projects each text into a fixed-dim vector using word hashing.
        Not semantically meaningful but allows cosine similarity to work.
        """
        dim = 384
        vecs = []
        for text in texts:
            vec = np.zeros(dim, dtype=np.float32)
            words = text.lower().split()
            for word in words:
                idx = hash(word) % dim
                vec[idx] += 1.0
            norm = np.linalg.norm(vec) + 1e-9
            vecs.append(vec / norm)
        arr = np.array(vecs, dtype=np.float32)
        logger.debug(f"[Embedder:Keyword] Embedded {len(texts)} texts → shape {arr.shape}")
        return arr

    # ------------------------------------------------------------------
    # Convenience: embed chunks
    # ------------------------------------------------------------------

    def embed_chunks(
        self, chunks: list[ArticleChunk], batch_size: int = 32
    ) -> list[tuple[ArticleChunk, np.ndarray]]:
        """
        Embed a list of ArticleChunk objects in batches.
        Returns list of (chunk, embedding_vector) pairs.
        """
        results: list[tuple[ArticleChunk, np.ndarray]] = []
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c.chunk_text for c in batch]
            vecs = self.embed_texts(texts)
            results.extend(zip(batch, vecs))

        logger.info(f"[Embedder] Embedded {len(chunks)} chunks (backend={self._backend})")
        return results

    @property
    def backend(self) -> EmbeddingBackend:
        return self._backend

    @property
    def embedding_dim(self) -> int:
        return 768 if self._backend == "gemini" else 384
