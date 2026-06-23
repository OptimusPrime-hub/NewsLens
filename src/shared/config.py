"""Type-safe application settings loaded from environment variables and .env."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Central configuration for all NewsLens modules."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # External APIs
    gemini_api_key: str = Field(default="", description="Primary Google Gemini API key")
    gemini_api_key_fallback: str = Field(
        default="",
        validation_alias=AliasChoices("GEMINI_API_KEY_FALLBACK", "GEMINI_FALLBACK_API_KEY"),
        description="Secondary Gemini API key used when the primary fails",
    )
    newsapi_key: str = Field(
        default="",
        validation_alias=AliasChoices("NEWSAPI_KEY", "NEWS_API_KEY"),
        description="NewsAPI key",
    )
    bing_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("BING_SEARCH_API_KEY", "BING_API_KEY"),
        description="Bing Search API v7 key",
    )
    bing_endpoint: str = Field(default="https://api.bing.microsoft.com/v7.0/search")
    tavily_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("TAVILY_API_KEY", "TAVILY_KEY"),
        description="Tavily AI Search API key (Tier-2 retrieval fallback)",
    )

    # Gemini-only model selection
    gemini_chat_model: str = Field(default="gemini-1.5-flash")
    gemini_embedding_model: str = Field(default="models/text-embedding-004")

    # Pathway VectorStore service
    pathway_host: str = Field(default="127.0.0.1")
    pathway_port: int = Field(default=8765)
    pathway_source_glob: str = Field(default="data/pathway_sources/*.json")
    pathway_refresh_interval_ms: int = Field(default=30000)
    pathway_rss_refresh_interval_ms: int = Field(default=60000)
    news_sync_query: str = Field(default="world news top stories")

    # Retrieval resilience demo controls. Example: "pathway,tavily,scraper"
    simulate_retrieval_failures: str = Field(default="")

    # CRAG thresholds
    crag_relevance_threshold: float = Field(
        default=0.72,
        ge=0.0,
        le=1.0,
        description="Minimum mean relevance to accept retrieval results",
    )
    m1_confidence_threshold: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Minimum confidence to accept intent parse",
    )

    # Agent graph
    max_agent_iterations: int = Field(default=3, ge=1)
    retrieval_top_k: int = Field(default=15, ge=1)

    # Local dev / demo
    seed_demo_data: bool = Field(default=False)

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_dir: str = Field(default="logs")

    @property
    def gemini_api_keys(self) -> list[str]:
        """Primary Gemini key first, then optional fallback (deduplicated)."""
        keys: list[str] = []
        for value in (self.gemini_api_key, self.gemini_api_key_fallback):
            key = value.strip()
            if key and key not in keys:
                keys.append(key)
        return keys

    @property
    def simulated_failure_set(self) -> set[str]:
        """Normalized retrieval callbacks that should fail for demos/tests."""
        return {
            item.strip().lower()
            for item in self.simulate_retrieval_failures.split(",")
            if item.strip()
        }


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Parse settings once and reuse the object."""
    return AppSettings()


get_config = get_settings
