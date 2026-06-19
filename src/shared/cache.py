"""
Shared caching utilities for resource-intensive models and settings.
"""

from __future__ import annotations

from typing import Any

from src.shared.config import AppSettings, get_settings
from src.shared.logging import get_logger

logger = get_logger(__name__)

# Global cache for heavy resources
_model_cache: dict[str, Any] = {}


def get_cached_settings() -> AppSettings:
    """
    Get cached application settings.
    Wrapper around get_settings which already uses lru_cache.
    """
    return get_settings()


def get_cached_model(key: str, factory_fn: callable, *args: Any, **kwargs: Any) -> Any:
    """
    Retrieve a cached model instance or initialize it using factory_fn.

    Args:
        key: Unique cache key identifier.
        factory_fn: Callable to instantiate the model if not cached.
        *args: Positional arguments for factory_fn.
        **kwargs: Keyword arguments for factory_fn.
    """
    if key in _model_cache:
        logger.debug("Model cache hit", key=key)
        return _model_cache[key]

    logger.info("Model cache miss, initializing model", key=key)
    try:
        model = factory_fn(*args, **kwargs)
        _model_cache[key] = model
        return model
    except Exception as exc:
        logger.error("Failed to initialize model", key=key, error=str(exc))
        raise
