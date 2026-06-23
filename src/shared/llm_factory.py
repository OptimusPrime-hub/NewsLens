"""
LLM provider factory with fallback chain.

Returns LangChain BaseChatModel instances.
Fallback order: Gemini → OpenAI → Anthropic → Ollama (local).
"""

from __future__ import annotations

from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

from src.shared.config import get_settings
from src.shared.exceptions import LLMProviderUnavailableError
from src.shared.logging import get_logger

logger = get_logger(__name__)

Provider = Literal["openai", "anthropic", "gemini", "ollama"]


def get_chat_model(
    provider: Provider = "openai",
    model: str | None = None,
    temperature: float = 0.0,
    purpose: Literal["m1", "m5"] = "m1",
) -> BaseChatModel:
    """
    Instantiate a chat model for the requested provider.

    Args:
        provider: Which LLM backend to use.
        model: Model name override (uses config default if None).
        temperature: Sampling temperature.
        purpose: What the LLM is being used for ("m1" or "m5").

    Returns:
        A LangChain BaseChatModel ready for `.ainvoke()`.

    Raises:
        LLMProviderUnavailableError: If the provider can't be initialised.
    """
    settings = get_settings()

    if provider == "openai":
        default_model = settings.m1_llm_model if purpose == "m1" else settings.m5_llm_model
        return _build_openai(model or default_model, temperature)
    if provider == "anthropic":
        return _build_anthropic(model or settings.secondary_chat_model, temperature)
    if provider == "gemini":
        return _build_gemini(model or settings.gemini_chat_model, temperature)
    if provider == "ollama":
        return _build_ollama(model or settings.local_chat_model, temperature)

    raise LLMProviderUnavailableError(f"Unknown provider: {provider}")


def get_chat_model_with_fallback(
    temperature: float = 0.0,
    purpose: Literal["m1", "m5"] = "m1",
) -> BaseChatModel:
    """
    Try Gemini → OpenAI → Anthropic → Ollama.  Return the first that initialises.

    Raises:
        LLMProviderUnavailableError: If every provider fails.
    """
    errors: list[str] = []
    for provider in ("gemini", "openai", "anthropic", "ollama"):
        try:
            llm = get_chat_model(provider=provider, temperature=temperature, purpose=purpose)  # type: ignore[arg-type]
            logger.info("LLM provider ready", provider=provider, purpose=purpose)
            return llm
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{provider}: {exc}")
            logger.warning("LLM provider unavailable", provider=provider, error=str(exc))

    raise LLMProviderUnavailableError(
        "All LLM providers unavailable",
        details={"errors": errors},
    )


def get_active_model_name(purpose: Literal["m1", "m5"] = "m1") -> str:
    """
    Get the name of the active chat model from the fallback chain.
    If all external LLM providers are unavailable, returns 'regex-fallback'.
    """
    try:
        llm = get_chat_model_with_fallback(purpose=purpose)
        if hasattr(llm, "model_name"):
            return getattr(llm, "model_name")
        if hasattr(llm, "model"):
            return getattr(llm, "model")
        return str(llm)
    except Exception:
        return "regex-fallback"


# ── Private builder helpers ──────────────────────────────────────────────────


def _build_openai(model: str, temperature: float) -> BaseChatModel:
    settings = get_settings()
    if not settings.openai_api_key:
        raise LLMProviderUnavailableError("OPENAI_API_KEY not set")

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.openai_api_key,
    )


def _build_anthropic(model: str, temperature: float) -> BaseChatModel:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise LLMProviderUnavailableError("ANTHROPIC_API_KEY not set")

    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=model,
        temperature=temperature,
        api_key=settings.anthropic_api_key,
    )


def _build_gemini(model: str, temperature: float) -> BaseChatModel:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise LLMProviderUnavailableError("GEMINI_API_KEY not set")

    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        google_api_key=settings.gemini_api_key,
    )


def _build_ollama(model: str, temperature: float) -> BaseChatModel:
    settings = get_settings()

    from langchain_community.chat_models import ChatOllama

    return ChatOllama(
        model=model,
        temperature=temperature,
        base_url=settings.ollama_base_url,
    )
