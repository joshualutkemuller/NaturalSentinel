"""Command-line interface for naturalsentinel."""

import argparse
import json
import logging
from pathlib import Path

from naturalsentinel.models import RegulatoryDomain
from naturalsentinel.providers.base import ModelProvider


def build_provider(provider_name: str, model: str | None = None) -> ModelProvider:
    """Factory to instantiate a provider from a CLI string."""
    match provider_name.lower():
        case "anthropic":
            from naturalsentinel.providers.anthropic import AnthropicProvider
            return AnthropicProvider(model=model or "claude-sonnet-4-20250514")
        case "openai":
            from naturalsentinel.providers.openai import OpenAIProvider
            return OpenAIProvider(model=model or "gpt-4o")
        case "gemini":
            from naturalsentinel.providers.gemini import GeminiProvider
            return GeminiProvider(model=model or "gemini-2.0-flash")
        case "ollama":
            from naturalsentinel.providers.ollama import OllamaProvider
            return OllamaProvider(model=model or "llama3.1")
        case "mock":
            from naturalsentinel.providers.mock import MockProvider
            return MockProvider()
        case _:
            raise ValueError(f"Unknown provider: {provider_name}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(
        prog="naturalsentinel",
        description="Regulatory Change Monitor & Impact Mapper",
    )
    parser.add_argument(
        "--provider", default="mock",
        choices=["anthropic", "openai", "gemini", "ollama", "mock"],
        help="LLM provider (default: mock for demo)",
    )
    parser.add_argument("--model", default=None, help="Specific model name override")
    parser.add_argument(
        "--domains", nargs="*", default=None,
        help="Regulatory domains to monitor (sec cfpb fed fda epa ustr)",
    )
    parser.add_argument("--days", type=int, default=60, help="Look-back window in days")
    parser.add_argument("--reset", action="store_true", help="Reset seen-filings state")
    parser.add_argument("--memory-db", default=None, help="Path to SQLite memory database")
    parser.add_argument("--output", default=None, help="Write JSON output to file")
    args = parser.parse_args()

    provider = build_provider(args.provider, args.model)
    domains = [RegulatoryDomain(d) for d in args.domains] if args.domains else None

    memory = None
    if args.memory_db:
        from naturalsentinel.memory.store import MemoryStore
        memory = MemoryStore(args.memory_db)

    from naturalsentinel.agent import RegulatoryMonitorAgent
    agent = RegulatoryMonitorAgent(
        provider=provider, domains=domains, memory=memory,
    )
    if args.reset:
        agent.reset_state()

    output = agent.run_json(since_days=args.days)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Results written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
