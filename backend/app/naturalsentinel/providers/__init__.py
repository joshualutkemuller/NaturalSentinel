"""LLM provider backends — swap with a single constructor argument."""

from app.naturalsentinel.providers.base import ModelProvider
from app.naturalsentinel.providers.mock import MockProvider

__all__ = ["ModelProvider", "MockProvider"]


# Lazy imports for real providers to avoid mandatory SDK deps
def get_anthropic_provider(*args, **kwargs):
    from app.naturalsentinel.providers.anthropic import AnthropicProvider

    return AnthropicProvider(*args, **kwargs)


def get_openai_provider(*args, **kwargs):
    from app.naturalsentinel.providers.openai import OpenAIProvider

    return OpenAIProvider(*args, **kwargs)


def get_gemini_provider(*args, **kwargs):
    from app.naturalsentinel.providers.gemini import GeminiProvider

    return GeminiProvider(*args, **kwargs)


def get_ollama_provider(*args, **kwargs):
    from app.naturalsentinel.providers.ollama import OllamaProvider

    return OllamaProvider(*args, **kwargs)
