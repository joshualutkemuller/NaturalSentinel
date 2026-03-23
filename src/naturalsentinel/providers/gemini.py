"""Google Gemini provider."""

import os

from naturalsentinel.providers.base import ModelProvider


class GeminiProvider(ModelProvider):
    """Google Gemini via the google-genai SDK."""

    def __init__(self, model: str = "gemini-2.0-flash", api_key: str | None = None):
        try:
            from google import genai
        except ImportError:
            raise ImportError("Google GenAI SDK not installed. Run: pip install google-genai")
        self.client = genai.Client(api_key=api_key or os.getenv("GOOGLE_API_KEY"))
        self.model = model

    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        from google.genai import types

        resp = self.client.models.generate_content(
            model=self.model,
            contents=f"{system}\n\n{user}",
            config=types.GenerateContentConfig(temperature=temperature, max_output_tokens=4096),
        )
        return resp.text

    def name(self) -> str:
        return f"Gemini/{self.model}"
