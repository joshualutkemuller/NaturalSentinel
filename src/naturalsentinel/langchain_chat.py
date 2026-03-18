"""Rich-formatted CLI chat shell with optional LangChain model integration."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from naturalsentinel.cli import analyze_local_documents, build_provider
from naturalsentinel.models import RegulatoryDomain

WELCOME_TEXT = "AI agent for reviewing regulatory filings, controls, and local documents"
COMMANDS = {
    "/attach <path>": "attach a supported local file for the next message",
    "/dir <path>": "approve a directory for quick attachment access",
    "/dirs": "list approved directories",
    "/tools": "list available tools",
    "/clear": "clear conversation history and pending attachments",
    "/help": "show this command reference",
    "/exit": "quit",
}

TOOL_NAMES = [
    "local_document_analysis",
    "memory_context",
    "directory_attachments",
    "chat_history",
]


@dataclass
class ChatState:
    session_name: str = "default"
    attached_paths: list[str] = field(default_factory=list)
    approved_dirs: list[str] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)


class LangChainUnavailableError(RuntimeError):
    """Raised when LangChain integrations are not available."""


def build_langchain_model(provider: str, model: str | None = None):
    """Build a LangChain chat model for supported providers."""
    provider = provider.lower()
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model or "claude-3-5-sonnet-latest", temperature=0)
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model or "gpt-4o", temperature=0)
    raise LangChainUnavailableError(
        "LangChain chat currently supports 'anthropic' and 'openai' providers in this shell."
    )


def build_header_lines(provider: str, session_name: str) -> list[str]:
    """Return the styled shell header content."""
    return [
        f"[bold green]NaturalSentinel[/bold green] · {WELCOME_TEXT}",
        f"Provider: {provider}  |  {len(TOOL_NAMES)} tools loaded  |  Session: {session_name}",
    ]


def render_command_table() -> str:
    """Render the slash-command reference in a screenshot-friendly layout."""
    lines = ["[bold]Commands[/bold]"]
    for command, description in COMMANDS.items():
        lines.append(f"[bold white]{command:<18}[/bold white] {description}")
    return "\n".join(lines)


def handle_command(state: ChatState, raw: str) -> str:
    """Apply a slash command to the current chat state."""
    raw = raw.strip()
    if raw.startswith("/attach "):
        path = str(Path(raw.split(" ", 1)[1]).expanduser().resolve())
        state.attached_paths.append(path)
        return f"Attached: {path}"
    if raw.startswith("/dir "):
        path = str(Path(raw.split(" ", 1)[1]).expanduser().resolve())
        state.approved_dirs.append(path)
        return f"Approved directory: {path}"
    if raw == "/dirs":
        return "\n".join(state.approved_dirs) if state.approved_dirs else "No approved directories yet."
    if raw == "/tools":
        return "\n".join(f"- {tool}" for tool in TOOL_NAMES)
    if raw == "/clear":
        state.attached_paths.clear()
        state.history.clear()
        return "Conversation history and attachments cleared."
    if raw == "/help":
        return render_command_table()
    if raw == "/exit":
        return "exit"
    return "Unknown command. Use /help."


def summarize_attachments(
    provider_name: str,
    domain: str,
    attachment_paths: list[str],
) -> list[dict[str, Any]]:
    """Analyze current attachments so the agent can answer with grounded context."""
    if not attachment_paths:
        return []
    provider = build_provider(provider_name)
    return analyze_local_documents(
        provider=provider,
        domain=RegulatoryDomain(domain),
        input_paths=attachment_paths,
        input_dir=None,
    )


def build_prompt(question: str, analyses: list[dict[str, Any]], state: ChatState) -> str:
    """Build the user payload sent to the LangChain model."""
    prompt = [
        "You are NaturalSentinel, a regulatory analysis CLI agent.",
        "Answer clearly and concisely using the attached document analyses when relevant.",
        f"Approved directories: {state.approved_dirs}",
        f"Attached analyses: {json.dumps(analyses, indent=2) if analyses else '[]'}",
        f"User question: {question}",
    ]
    return "\n\n".join(prompt)


def fallback_answer(question: str, analyses: list[dict[str, Any]]) -> str:
    """Fallback output when a LangChain model is unavailable."""
    if analyses:
        first = analyses[0]
        return (
            f"I analyzed {len(analyses)} attached document(s). "
            f"Top item: {first['filing']['title']} | severity={first['impact']['severity']} | "
            f"summary={first['impact']['risk_summary']}\n\n"
            f"Question received: {question}\n"
            "Install LangChain provider dependencies to enable full conversational answers."
        )
    return (
        "No attached documents were analyzed for this turn. "
        "Install LangChain provider dependencies and configure a supported provider "
        "for model-backed conversational responses."
    )


def chat_once(
    provider_name: str,
    model_name: str | None,
    domain: str,
    question: str,
    state: ChatState,
) -> str:
    """Process one user turn."""
    analyses = summarize_attachments(provider_name, domain, state.attached_paths)
    state.history.append({"role": "user", "content": question})

    try:
        model = build_langchain_model(provider_name, model_name)
    except Exception:
        answer = fallback_answer(question, analyses)
        state.history.append({"role": "assistant", "content": answer})
        state.attached_paths.clear()
        return answer

    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    messages = [SystemMessage(content="You are NaturalSentinel, a styled CLI regulatory agent.")]
    for item in state.history[:-1]:
        msg_cls = HumanMessage if item["role"] == "user" else AIMessage
        messages.append(msg_cls(content=item["content"]))
    messages.append(HumanMessage(content=build_prompt(question, analyses, state)))
    response = model.invoke(messages)
    answer = response.content if hasattr(response, "content") else str(response)
    state.history.append({"role": "assistant", "content": answer})
    state.attached_paths.clear()
    return answer


def build_parser() -> argparse.ArgumentParser:
    """Build the chat-shell parser."""
    parser = argparse.ArgumentParser(
        prog="naturalsentinel-chat",
        description="Styled NaturalSentinel chat shell",
    )
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--model", default=None)
    parser.add_argument("--domain", default="sec")
    parser.add_argument("--session", default="default")
    return parser


def main() -> None:
    """Run the styled CLI chat shell."""
    parser = build_parser()
    args = parser.parse_args()

    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    state = ChatState(session_name=args.session)

    console.print(
        Panel(
            "\n".join(build_header_lines(args.provider, args.session))
            + "\n\n"
            + render_command_table()
        )
    )

    while True:
        raw = console.input("[bold cyan]> [/bold cyan]")
        if raw.startswith("/"):
            result = handle_command(state, raw)
            if result == "exit":
                break
            console.print(result)
            continue
        console.print("[dim]Thinking...[/dim]")
        answer = chat_once(args.provider, args.model, args.domain, raw, state)
        console.print(answer)


if __name__ == "__main__":
    main()
