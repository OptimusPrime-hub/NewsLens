"""
Local in-process retriever.

Connects to the IngestionPipeline's in-memory chunk store and performs
cosine similarity search using pre-computed embeddings.
Used as the primary retriever (Tier 0) on Windows and Vercel deployments.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.m2_agents.retrieval.base import BaseRetriever
from src.m2_agents.schemas import RetrievedChunk
from src.shared.logging import get_logger

logger = get_logger(__name__)


class LocalRetriever(BaseRetriever):
    """Retrieves chunks from the in-process IngestionPipeline vector store."""

    @property
    def tier_name(self) -> str:
        return "local"

    async def retrieve(
        self,
        query: str,
        *,
        filters: dict | None = None,
        top_k: int = 15,
    ) -> list[RetrievedChunk]:
        """
        Query the in-process chunk store via the IngestionPipeline singleton.

        This retriever:
        1. Gets or creates the pipeline singleton
        2. If the pipeline has no chunks, triggers a poll cycle to fetch articles
        3. Embeds the query and runs cosine similarity search
        4. Converts results to RetrievedChunk models

        Args:
            query: Natural language search query.
            filters: Metadata filters (currently unused for local store).
            top_k: Number of results to request.

        Returns:
            List of RetrievedChunk sorted by relevance descending.
        """
        from src.m0_ingestion.pipeline import get_pipeline

        pipeline = get_pipeline(query=query)

        # Auto-ingest if the store is empty
        if pipeline.chunk_count == 0:
            logger.info("[LocalRetriever] Store empty — running ingestion poll")
            pipeline._poll_once()

        if pipeline.chunk_count == 0:
            logger.warning("[LocalRetriever] Still no chunks after ingestion")
            return []

        # Embed the query using the same embedder
        q_vec = pipeline.embedder.embed_texts([query])[0].tolist()

        # Run cosine similarity search
        raw_results = pipeline.similarity_search(q_vec, top_k=top_k)

        # Convert to RetrievedChunk models
        chunks: list[RetrievedChunk] = []
        for chunk, score in raw_results:
            try:
                rc = RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    chunk_text=chunk.chunk_text,
                    publisher=chunk.publisher or "unknown",
                    publish_ts=chunk.publish_ts or datetime.now(tz=UTC),
                    relevance_score=float(score),
                    source_url=chunk.url or "",
                )
                chunks.append(rc)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning("Skipping malformed local chunk", error=str(exc))
                continue

        logger.info(
            "[LocalRetriever] Retrieved chunks",
            n_chunks=len(chunks),
            top_score=f"{chunks[0].relevance_score:.3f}" if chunks else "N/A",
        )
        return chunks

    async def close(self) -> None:
        """No resources to release for in-process retriever."""
