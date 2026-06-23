"""
Application settings loaded from environment / .env file.

Uses pydantic-settings for type-safe configuration.
All secrets come from env vars — never hardcode.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Central configuration for all NewsLens modules."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM Providers ────────────────────────────────────────────────────────
    openai_api_key: str = Field(default="", description="OpenAI API key")
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    gemini_api_key: str = Field(default="", description="Gemini API key")
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL for local LLM fallback",
    )
    groq_api_key: str = Field(default="", description="Groq API key")
    newsapi_key: str = Field(default="", description="NewsAPI API key")



    # ── Model Selection ──────────────────────────────────────────────────────
    m1_llm_model: str = Field(default="gpt-4o-mini")
    m5_llm_model: str = Field(default="gpt-4o")
    primary_chat_model: str = Field(default="gpt-4o-mini")
    secondary_chat_model: str = Field(default="claude-3-5-haiku-20241022")
    gemini_chat_model: str = Field(default="gemini-1.5-flash")
    local_chat_model: str = Field(default="llama3.2:3b")
    embedding_model: str = Field(default="text-embedding-3-small")
    local_embedding_model: str = Field(default="BAAI/bge-small-en-v1.5")

    # ── Pathway VectorStore ──────────────────────────────────────────────────
    pathway_host: str = Field(default="127.0.0.1")
    pathway_port: int = Field(default=8765)
    pathway_refresh_interval_ms: int = Field(
        default=30000,
        description="Pathway poll refresh interval in ms",
    )
    pathway_rss_refresh_interval_ms: int = Field(
        default=60000,
        description="Pathway RSS poll refresh interval in ms",
    )


    # ── Bing Search ──────────────────────────────────────────────────────────
    bing_api_key: str = Field(default="", description="Bing Search API v7 key")
    bing_endpoint: str = Field(
        default="https://api.bing.microsoft.com/v7.0/search",
    )

    # ── CRAG Thresholds ──────────────────────────────────────────────────────
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

    # ── Agent Graph ──────────────────────────────────────────────────────────
    max_agent_iterations: int = Field(
        default=3,
        ge=1,
        description="Max re-invocations before returning partial result",
    )
    retrieval_top_k: int = Field(default=15, ge=1)

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
    )
    log_dir: str = Field(default="logs")


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Singleton accessor — parses .env once and caches."""
    return AppSettings()


# Alias for backward compatibility with M0 and M1 imports
get_config = get_settings

