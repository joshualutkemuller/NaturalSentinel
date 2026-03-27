"""Abstract base class for all LLM providers."""

from abc import ABC, abstractmethod


class ModelProvider(ABC):
    """Interface that all LLM backends must implement."""

    @abstractmethod
    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        """Send a system + user prompt pair and return the model's text response."""

    @abstractmethod
    def name(self) -> str:
        """Human-readable provider/model identifier, e.g. 'Anthropic/claude-sonnet-4-20250514'."""
