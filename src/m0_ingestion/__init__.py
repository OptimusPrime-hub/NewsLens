"""M0 — Live News Ingestion package."""

from src.m0_ingestion.document_store import document_store
from src.m0_ingestion.pipeline import IngestionPipeline, get_pipeline
from src.m0_ingestion.schemas import ArticleChunk, NormalizedArticle, RawArticle

__all__ = [
    "get_pipeline",
    "IngestionPipeline",
    "document_store",
    "RawArticle",
    "NormalizedArticle",
    "ArticleChunk",
]
