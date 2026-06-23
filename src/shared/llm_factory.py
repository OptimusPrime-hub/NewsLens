"""Gemini LangChain chat model factory with API-key fallback."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from src.shared.config import get_settings
from src.shared.exceptions import LLMProviderUnavailableError
from src.shared.logging import get_logger

logger = get_logger(__name__)


def _build_gemini_model(
    api_key: str,
    *,
    model: str,
    temperature: float,
    purpose: str,
    key_label: str,
) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    logger.info(
        "LLM provider ready",
        provider="gemini",
        model=model,
        purpose=purpose,
        key=key_label,
    )
    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        google_api_key=api_key,
    )


def get_chat_model(
    model: str | None = None,
    temperature: float = 0.0,
    purpose: str = "m1",
) -> BaseChatModel:
    """Instantiate the configured Gemini chat model using the primary API key."""
    settings = get_settings()
    keys = settings.gemini_api_keys
    if not keys:
        raise LLMProviderUnavailableError("GEMINI_API_KEY not set")

    selected_model = model or settings.gemini_chat_model
    return _build_gemini_model(
        keys[0],
        model=selected_model,
        temperature=temperature,
        purpose=purpose,
        key_label="primary",
    )


def get_chat_model_with_fallback(
    temperature: float = 0.0,
    purpose: str = "m1",
) -> BaseChatModel:
    """Return Gemini chat model; automatically falls back to the secondary API key."""
    settings = get_settings()
    keys = settings.gemini_api_keys
    if not keys:
        raise LLMProviderUnavailableError("GEMINI_API_KEY not set")

    selected_model = settings.gemini_chat_model
    primary = _build_gemini_model(
        keys[0],
        model=selected_model,
        temperature=temperature,
        purpose=purpose,
        key_label="primary",
    )

    if len(keys) == 1:
        return primary

    secondary = _build_gemini_model(
        keys[1],
        model=selected_model,
        temperature=temperature,
        purpose=purpose,
        key_label="fallback",
    )
    logger.info("Gemini fallback key configured", purpose=purpose)
    return primary.with_fallbacks([secondary])


def get_active_model_name(purpose: str = "m1") -> str:
    """Return the active Gemini model name, or regex-fallback when unavailable."""
    try:
        llm = get_chat_model_with_fallback(purpose=purpose)
        if hasattr(llm, "model_name"):
            return str(getattr(llm, "model_name"))
        if hasattr(llm, "model"):
            return str(getattr(llm, "model"))
        return str(llm)
    except Exception:
        return "regex-fallback"
