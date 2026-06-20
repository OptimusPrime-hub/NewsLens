"""
M0 — Embedder
Converts ArticleChunk text into dense vector embeddings.

Primary:  OpenAI text-embedding-3-small  (1536-dim)
Fallback: sentence-transformers BAAI/bge-small-en-v1.5  (384-dim, local)

The fallback activates automatically on any OpenAI API error so the
pipeline continues without human intervention.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from loguru import logger

from src.m0_ingestion.schemas import ArticleChunk
from src.shared.config import get_config

config = get_config()

EmbeddingBackend = Literal["openai", "local"]


class Embedder:
    """
    Embed texts using OpenAI or fall back to a local sentence-transformer.
    All methods return numpy float32 arrays of shape (N, dim).
    """

    def __init__(self) -> None:
        self._openai_client = None
        self._local_model = None
        self._backend: EmbeddingBackend = "openai"

    # ------------------------------------------------------------------
    # Lazy initialisation
    # ------------------------------------------------------------------

    def _get_openai(self):
        if self._openai_client is None:
            import openai  # noqa: PLC0415
            self._openai_client = openai.OpenAI(api_key=config.openai_api_key)
        return self._openai_client

    def _get_local(self):
        if self._local_model is None:
            logger.info(f"[Embedder] Loading local model: {config.local_embedding_model}")
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
            self._local_model = SentenceTransformer(config.local_embedding_model)
        return self._local_model

    # ------------------------------------------------------------------
    # Core embedding methods
    # ------------------------------------------------------------------

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """
        Embed a list of strings. Returns float32 ndarray (N, dim).
        Tries OpenAI first; silently switches to local on any error.
        """
        if not texts:
            return np.empty((0, 384), dtype=np.float32)

        if self._backend == "openai" and config.openai_api_key:
            try:
                return self._embed_openai(texts)
            except Exception as exc:
                logger.warning(f"[Embedder] OpenAI failed ({exc}); switching to local model")
                self._backend = "local"

        return self._embed_local(texts)

    def _embed_openai(self, texts: list[str]) -> np.ndarray:
        client = self._get_openai()
        resp = client.embeddings.create(
            model=config.embedding_model,
            input=texts,
        )
        vecs = [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
        arr = np.array(vecs, dtype=np.float32)
        logger.debug(f"[Embedder:OpenAI] Embedded {len(texts)} texts → shape {arr.shape}")
        return arr

    def _embed_local(self, texts: list[str]) -> np.ndarray:
        model = self._get_local()
        arr = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        logger.debug(f"[Embedder:Local] Embedded {len(texts)} texts → shape {arr.shape}")
        return arr.astype(np.float32)

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
        return 1536 if self._backend == "openai" else 384
