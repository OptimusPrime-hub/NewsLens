"""
NewsLens custom exception hierarchy.

All module-specific errors inherit from NewsLensError so callers
can catch broadly or narrowly depending on their needs.
"""


class NewsLensError(Exception):
    """Base exception for all NewsLens errors."""

    def __init__(self, message: str = "", *, details: dict | None = None) -> None:
        self.details = details or {}
        super().__init__(message)


# ── Retrieval Errors ─────────────────────────────────────────────────────────


class RetrievalError(NewsLensError):
    """A retrieval source failed to return results."""


class PathwayRetrievalError(RetrievalError):
    """Pathway VectorStore query failed."""


class BingRetrievalError(RetrievalError):
    """Bing Search API call failed."""


class ScraperRetrievalError(RetrievalError):
    """Web scraper failed to fetch or parse content."""


class FallbackExhaustedError(RetrievalError):
    """All retrieval tiers exhausted — no data available."""


# ── LLM Errors ───────────────────────────────────────────────────────────────


class LLMError(NewsLensError):
    """An LLM provider call failed."""


class LLMParsingError(LLMError):
    """LLM returned output that could not be parsed into the expected schema."""


class LLMProviderUnavailableError(LLMError):
    """No LLM provider is reachable."""


# ── CRAG Errors ──────────────────────────────────────────────────────────────


class CRAGError(NewsLensError):
    """CRAG evaluation or query rewriting failed."""


# ── Validation Errors ────────────────────────────────────────────────────────


class ResultValidationError(NewsLensError):
    """Final result assembly failed validation checks."""
