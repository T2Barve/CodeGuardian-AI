from typing import Optional
import structlog
from app.config.settings import settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.gemini import GeminiProvider
from app.services.llm.mock import MockLLMProvider

logger = structlog.get_logger(__name__)


def get_llm_provider(
    provider_type: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
) -> BaseLLMProvider:
    """
    Factory function for obtaining an LLM provider instance.
    
    Adheres to Rule 37: Dynamic Provider Selection without agent coupling.
    Defaults to MockLLMProvider if API key is absent or provider is 'mock'.
    """
    active_provider = (provider_type or settings.LLM_PROVIDER).lower()
    active_key = api_key if api_key is not None else settings.LLM_API_KEY
    active_model = model_name or settings.LLM_MODEL_NAME

    if active_provider in ("gemini", "google"):
        if not active_key or active_key.strip() == "":
            logger.warning(
                "Gemini provider selected but LLM_API_KEY is unset; falling back to MockLLMProvider for safety."
            )
            return MockLLMProvider(model_name=f"mock-{active_model}")
        return GeminiProvider(api_key=active_key, model_name=active_model)

    elif active_provider in ("mock", "test"):
        return MockLLMProvider(model_name=active_model)

    else:
        logger.warning(
            f"Unsupported LLM provider '{active_provider}'; falling back to MockLLMProvider."
        )
        return MockLLMProvider(model_name=f"fallback-{active_model}")
