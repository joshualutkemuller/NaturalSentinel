"""Ollama provider for local models."""

import json
import urllib.request

from naturalsentinel.providers.base import ModelProvider


class OllamaProvider(ModelProvider):
    """Local models via the Ollama REST API."""

    def __init__(self, model: str = "llama3.1", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "stream": False,
                "options": {"temperature": temperature},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        ).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        return data["message"]["content"]

    def name(self) -> str:
        return f"Ollama/{self.model}"
