"""
Shared module — cross-cutting infrastructure used by all NewsLens modules.
"""

from src.shared.config import AppSettings, get_settings
from src.shared.exceptions import (
    CRAGError,
    FallbackExhaustedError,
    LLMError,
    LLMParsingError,
    LLMProviderUnavailableError,
    NewsLensError,
    RetrievalError,
    ResultValidationError,
)
from src.shared.llm_factory import get_chat_model, get_chat_model_with_fallback
from src.shared.logging import get_logger, setup_logger

__all__ = [
    "AppSettings",
    "CRAGError",
    "FallbackExhaustedError",
    "LLMError",
    "LLMParsingError",
    "LLMProviderUnavailableError",
    "NewsLensError",
    "RetrievalError",
    "ResultValidationError",
    "get_chat_model",
    "get_chat_model_with_fallback",
    "get_logger",
    "get_settings",
    "setup_logger",
]
