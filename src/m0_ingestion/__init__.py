"""M0 — Live News Ingestion package."""

from src.m0_ingestion.pipeline import get_pipeline, IngestionPipeline
from src.m0_ingestion.document_store import document_store
from src.m0_ingestion.schemas import RawArticle, NormalizedArticle, ArticleChunk

__all__ = [
    "get_pipeline",
    "IngestionPipeline",
    "document_store",
    "RawArticle",
    "NormalizedArticle",
    "ArticleChunk",
]