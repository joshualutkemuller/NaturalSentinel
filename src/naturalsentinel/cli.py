"""Command-line interface for naturalsentinel."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from naturalsentinel.agent_framework import AgentRuntime
from naturalsentinel.models import ChangeType, RegulatoryDomain, RegulatoryFiling
from naturalsentinel.providers.base import ModelProvider
from naturalsentinel.skills import ALL_SKILLS
from naturalsentinel.utils.serialization import enum_serializer

logger = logging.getLogger(__name__)

TEXT_SUFFIXES = {".txt", ".md", ".rst", ".log", ".text"}
STRUCTURED_SUFFIXES = {".json"}
WEB_SUFFIXES = {".html", ".htm"}
SUPPORTED_SUFFIXES = TEXT_SUFFIXES | STRUCTURED_SUFFIXES | WEB_SUFFIXES


def create_runtime(
    provider: ModelProvider,
    *,
    memory=None,
    state_path: str = "monitor_state.json",
) -> AgentRuntime:
    """Build an AgentRuntime preloaded with the full built-in skill library."""
    runtime = AgentRuntime(provider=provider, memory=memory, state_path=state_path)
    runtime.register_skills(*ALL_SKILLS)
    return runtime


def _serialize_runtime_results(results: list[dict]) -> list[dict]:
    """Normalize runtime scan/analyze results into JSON-safe dicts."""
    return json.loads(json.dumps(results, default=enum_serializer))


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


def _read_document_text(path: Path) -> str:
    """Read a supported local document into text for analysis."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"Unsupported file type for {path.name}: {suffix or '<none>'}. "
            f"Supported types: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )

    raw = path.read_text(encoding="utf-8")
    if suffix in STRUCTURED_SUFFIXES:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if isinstance(parsed, (dict, list)):
            return json.dumps(parsed, indent=2)
    return raw


def _collect_input_files(
    input_paths: list[str] | None,
    input_dir: str | None,
    recursive: bool,
) -> list[Path]:
    """Collect supported files from explicit paths and/or a directory."""
    files: list[Path] = []

    for raw_path in input_paths or []:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Input path does not exist: {path}")
        if path.is_file():
            files.append(path)
            continue
        if path.is_dir():
            iterator = path.rglob("*") if recursive else path.glob("*")
            files.extend(
                p for p in iterator if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
            )
            continue
        raise ValueError(f"Unsupported input path: {path}")

    if input_dir:
        directory = Path(input_dir).expanduser().resolve()
        if not directory.exists() or not directory.is_dir():
            raise FileNotFoundError(f"Input directory does not exist: {directory}")
        iterator = directory.rglob("*") if recursive else directory.glob("*")
        files.extend(p for p in iterator if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES)

    unique_files = sorted({p.resolve() for p in files})
    if not unique_files:
        raise ValueError("No supported input documents found.")
    return unique_files


def _slugify(value: str) -> str:
    chars = [c.lower() if c.isalnum() else "-" for c in value]
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "document"


def build_local_filings(
    input_paths: list[str] | None,
    input_dir: str | None,
    domain: RegulatoryDomain,
    recursive: bool = True,
) -> list[RegulatoryFiling]:
    """Build pseudo-filings from local documents so they can flow through the agent."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d")
    filings: list[RegulatoryFiling] = []

    for index, path in enumerate(_collect_input_files(input_paths, input_dir, recursive), start=1):
        filings.append(
            RegulatoryFiling(
                id=f"LOCAL-{domain.value.upper()}-{index:04d}-{_slugify(path.stem)[:32]}",
                title=path.stem.replace("_", " ").replace("-", " ").strip() or path.name,
                domain=domain,
                source_url=path.as_uri(),
                published_date=timestamp,
                raw_text=_read_document_text(path),
                change_type=ChangeType.NOTICE,
            )
        )
    return filings


def analyze_local_documents(
    provider: ModelProvider,
    domain: RegulatoryDomain,
    input_paths: list[str] | None,
    input_dir: str | None,
    recursive: bool = True,
    memory_db: str | None = None,
    state_path: str = "monitor_state.local.json",
) -> list[dict]:
    """Analyze local documents by routing them through public runtime skills."""
    memory = None
    if memory_db:
        from naturalsentinel.memory.store import MemoryStore

        memory = MemoryStore(memory_db)

    runtime = create_runtime(provider, memory=memory, state_path=state_path)

    try:
        filings = build_local_filings(input_paths, input_dir, domain, recursive=recursive)
        results: list[dict] = []
        for filing in filings:
            filing_data = json.loads(json.dumps(filing.model_dump(), default=enum_serializer))
            context_result = runtime.execute_skill(
                "build_context",
                {"domain": filing.domain.value, "filing_text": filing.raw_text},
            )
            analysis_result = runtime.execute_skill(
                "analyze_filing",
                {
                    "filing": filing_data,
                    "memory_context": context_result.data if context_result.success else "",
                },
            )
            if not analysis_result.success:
                raise RuntimeError(f"Failed to analyze {filing.id}: {analysis_result.error}")

            impact = analysis_result.data
            if memory is not None:
                runtime.execute_skill(
                    "store_memory",
                    {"filing_id": filing.id, "filing": filing_data, "impact": impact},
                )

            results.append({"filing": filing_data, "impact": impact})
        return _serialize_runtime_results(results)
    finally:
        if memory:
            memory.close()


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="naturalsentinel",
        description="Regulatory Change Monitor & Impact Mapper",
    )
    parser.add_argument(
        "--provider",
        default="mock",
        choices=["anthropic", "openai", "gemini", "ollama", "mock"],
        help="LLM provider (default: mock for demo)",
    )
    parser.add_argument("--model", default=None, help="Specific model name override")
    parser.add_argument(
        "--domains",
        nargs="*",
        default=None,
        help="Regulatory domains to monitor (sec cfpb fed fda epa ustr fhfa occ finra cftc fdic basel)",
    )
    parser.add_argument("--days", type=int, default=60, help="Look-back window in days")
    parser.add_argument("--reset", action="store_true", help="Reset seen-filings state")
    parser.add_argument("--memory-db", default=None, help="Path to SQLite memory database")
    parser.add_argument("--output", default=None, help="Write JSON output to file")
    parser.add_argument(
        "--input-path",
        dest="input_paths",
        action="append",
        default=None,
        help="Path to a local document file or directory to analyze",
    )
    parser.add_argument("--input-dir", default=None, help="Directory of local documents to analyze")
    parser.add_argument(
        "--input-domain",
        default="sec",
        help="Domain label to assign to local document analysis (default: sec)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not recurse when reading input directories",
    )
    return parser


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    parser = build_parser()
    args = parser.parse_args()

    provider = build_provider(args.provider, args.model)

    if args.input_paths or args.input_dir:
        output = json.dumps(
            analyze_local_documents(
                provider=provider,
                domain=RegulatoryDomain(args.input_domain.lower()),
                input_paths=args.input_paths,
                input_dir=args.input_dir,
                recursive=not args.no_recursive,
                memory_db=args.memory_db,
            ),
            indent=2,
            default=enum_serializer,
        )
    else:
        domains = [RegulatoryDomain(d) for d in args.domains] if args.domains else None

        memory = None
        if args.memory_db:
            from naturalsentinel.memory.store import MemoryStore

            memory = MemoryStore(args.memory_db)

        runtime = create_runtime(
            provider,
            memory=memory,
            state_path="monitor_state.json",
        )
        scan_params = {"since_days": args.days}
        if domains:
            scan_params["domains"] = [domain.value for domain in domains]
        if args.reset:
            Path(runtime.state_path).write_text(json.dumps({"seen_ids": []}))

        try:
            result = runtime.execute_skill("scan_cycle", scan_params)
            if not result.success:
                raise RuntimeError(result.error)
            output = json.dumps(
                _serialize_runtime_results(result.data["results"]),
                indent=2,
                default=enum_serializer,
            )
        finally:
            if memory:
                memory.close()

    if args.output:
        Path(args.output).write_text(output)
        print(f"Results written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
