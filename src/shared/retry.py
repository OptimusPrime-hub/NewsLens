"""
Shared retry decorators for LLMs and network operations.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar, cast

from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.shared.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def retry_llm(max_attempts: int = 3, min_wait: float = 2.0, max_wait: float = 10.0) -> Callable[[F], F]:
    """
    Decorator to retry LLM invocations with exponential backoff.
    Suitable for handling rate limits (429) or transient provider errors.
    """
    from openai import APIError as OpenAIAPIError
    # We catch common API errors
    exceptions_to_retry = (OpenAIAPIError,)
    try:
        from anthropic import APIError as AnthropicAPIError
        exceptions_to_retry += (AnthropicAPIError,)
    except ImportError:
        pass

    decorator = AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1.0, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(exceptions_to_retry),
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True,
    )

    def wrapper(func: F) -> F:
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            async for attempt in decorator:
                with attempt:
                    return await func(*args, **kwargs)
        return cast(F, wrapped)

    return wrapper


def retry_http(max_attempts: int = 3, min_wait: float = 1.0, max_wait: float = 5.0) -> Callable[[F], F]:
    """
    Decorator to retry HTTP network requests with exponential backoff.
    """
    import httpx

    decorator = AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1.0, min=min_wait, max=max_wait),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.NetworkError)),
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True,
    )

    def wrapper(func: F) -> F:
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            async for attempt in decorator:
                with attempt:
                    return await func(*args, **kwargs)
        return cast(F, wrapped)

    return wrapper
