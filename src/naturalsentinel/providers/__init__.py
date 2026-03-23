"""LLM provider backends — swap with a single constructor argument."""

from naturalsentinel.providers.base import ModelProvider
from naturalsentinel.providers.mock import MockProvider

__all__ = ["ModelProvider", "MockProvider"]


# Lazy imports for real providers to avoid mandatory SDK deps
def get_anthropic_provider(*args, **kwargs):
    from naturalsentinel.providers.anthropic import AnthropicProvider

    return AnthropicProvider(*args, **kwargs)


def get_openai_provider(*args, **kwargs):
    from naturalsentinel.providers.openai import OpenAIProvider

    return OpenAIProvider(*args, **kwargs)


def get_gemini_provider(*args, **kwargs):
    from naturalsentinel.providers.gemini import GeminiProvider

    return GeminiProvider(*args, **kwargs)


def get_ollama_provider(*args, **kwargs):
    from naturalsentinel.providers.ollama import OllamaProvider

    return OllamaProvider(*args, **kwargs)
