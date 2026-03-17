"""OpenAI GPT provider."""

import os
from naturalsentinel.providers.base import ModelProvider


class OpenAIProvider(ModelProvider):
    """GPT-4o / o1 / o3 via the OpenAI SDK."""

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("OpenAI SDK not installed. Run: pip install openai")
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model

    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content

    def name(self) -> str:
        return f"OpenAI/{self.model}"
