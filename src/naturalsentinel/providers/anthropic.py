"""Anthropic Claude provider."""

import os
from naturalsentinel.providers.base import ModelProvider


class AnthropicProvider(ModelProvider):
    """Claude via the Anthropic SDK."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("Anthropic SDK not installed. Run: pip install anthropic")
        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model

    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text

    def name(self) -> str:
        return f"Anthropic/{self.model}"
