"""
explore_mcp_servers.py — Interactive MCP Server Exploration Demo
================================================================

Demonstrates how NaturalSentinel can act as an MCP *client* and connect to
six different external MCP servers to augment regulatory monitoring:

  1. Filesystem  — browse local regulatory documents
  2. Fetch       — pull live regulatory web pages
  3. Brave Search — discover breaking regulatory news (requires BRAVE_API_KEY)
  4. Memory MCP  — shared knowledge-graph backend (alternative to memory.py)
  5. SQLite      — query an existing compliance database
  6. Time        — timezone-aware deadline handling

Prerequisites
-------------
  Node.js >= 18  (for the npm-distributed servers)
  pip install 'naturalsentinel[mcp]'
  pip install mcp-server-sqlite mcp-server-time   # Python servers

Run:
  python examples/explore_mcp_servers.py               # run all
  python examples/explore_mcp_servers.py --server fetch # run one
  python examples/explore_mcp_servers.py --list         # list servers
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Ensure the package is importable when running from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from naturalsentinel.mcp.external_servers import (
    SERVER_REGISTRY,
    print_registry_summary,
    run_brave_search_demo,
    run_fetch_demo,
    run_filesystem_demo,
    run_memory_mcp_demo,
    run_sqlite_demo,
    run_time_demo,
)


# ---------------------------------------------------------------------------
# Individual server runners
# ---------------------------------------------------------------------------


async def demo_filesystem() -> None:
    print("\n" + "─" * 60)
    print("  SERVER 1: Filesystem MCP")
    print("─" * 60)
    print("  Scenario: Browse local copies of regulatory filings.")
    print("  Value:    Ingest PDFs / text exports without a custom parser.\n")
    try:
        results = await run_filesystem_demo("/tmp")
        print(f"  Completed: {len(results)} tool calls")
    except FileNotFoundError:
        print("  SKIP: Node.js / npx not found. Install Node.js >= 18.")
    except Exception as exc:
        print(f"  SKIP: {exc}")


async def demo_fetch() -> None:
    print("\n" + "─" * 60)
    print("  SERVER 2: Fetch MCP")
    print("─" * 60)
    print("  Scenario: Retrieve a live Federal Reserve H.15 page.")
    print("  Value:    General-purpose URL retrieval mid-analysis.\n")
    try:
        results = await run_fetch_demo()
        print(f"  Completed: {len(results)} tool calls")
    except FileNotFoundError:
        print("  SKIP: Node.js / npx not found. Install Node.js >= 18.")
    except Exception as exc:
        print(f"  SKIP: {exc}")


async def demo_brave_search() -> None:
    print("\n" + "─" * 60)
    print("  SERVER 3: Brave Search MCP")
    print("─" * 60)
    print("  Scenario: Search for SEC enforcement news and Basel III updates.")
    print("  Value:    Surface breaking regulatory developments before")
    print("            they appear in the Federal Register.\n")
    if not os.getenv("BRAVE_API_KEY"):
        print("  SKIP: BRAVE_API_KEY not set. Export your key to run this demo.")
        return
    try:
        results = await run_brave_search_demo()
        print(f"  Completed: {len(results)} tool calls")
    except FileNotFoundError:
        print("  SKIP: Node.js / npx not found. Install Node.js >= 18.")
    except Exception as exc:
        print(f"  SKIP: {exc}")


async def demo_memory_mcp() -> None:
    print("\n" + "─" * 60)
    print("  SERVER 4: Memory MCP (Anthropic's knowledge-graph server)")
    print("─" * 60)
    print("  Scenario: Store regulatory entities in a shared knowledge graph.")
    print("  Value:    Any MCP client (Claude Desktop, Cursor, dashboards)")
    print("            can read the same regulatory entity graph — unlike")
    print("            NaturalSentinel's SQLite-backed memory.py which is")
    print("            local-only.  Use alongside memory.py or as migration.\n")
    try:
        results = await run_memory_mcp_demo()
        print(f"  Completed: {len(results)} tool calls")
    except FileNotFoundError:
        print("  SKIP: Node.js / npx not found. Install Node.js >= 18.")
    except Exception as exc:
        print(f"  SKIP: {exc}")


async def demo_sqlite() -> None:
    print("\n" + "─" * 60)
    print("  SERVER 5: SQLite MCP")
    print("─" * 60)
    print("  Scenario: Query an existing compliance findings database to")
    print("            cross-reference new regulatory impact assessments.")
    print("  Value:    No ETL pipelines needed — query live compliance records.\n")
    try:
        results = await run_sqlite_demo()
        print(f"  Completed: {len(results)} tool calls")
    except ModuleNotFoundError:
        print("  SKIP: mcp-server-sqlite not installed.")
        print("        Run: pip install mcp-server-sqlite")
    except Exception as exc:
        print(f"  SKIP: {exc}")


async def demo_time() -> None:
    print("\n" + "─" * 60)
    print("  SERVER 6: Time MCP")
    print("─" * 60)
    print("  Scenario: Calculate whether an SEC comment period (Eastern Time)")
    print("            is still open when the server runs in a different TZ.")
    print("  Value:    Accurate, LLM-injected timestamps and TZ conversion.\n")
    try:
        results = await run_time_demo()
        print(f"  Completed: {len(results)} tool calls")
    except ModuleNotFoundError:
        print("  SKIP: mcp-server-time not installed.")
        print("        Run: pip install mcp-server-time")
    except Exception as exc:
        print(f"  SKIP: {exc}")


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

DEMOS: dict[str, tuple[str, asyncio.coroutines]] = {
    "filesystem": ("Filesystem MCP", demo_filesystem),
    "fetch": ("Fetch MCP", demo_fetch),
    "brave-search": ("Brave Search MCP", demo_brave_search),
    "memory": ("Memory MCP", demo_memory_mcp),
    "sqlite": ("SQLite MCP", demo_sqlite),
    "time": ("Time MCP", demo_time),
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main(server: str | None = None) -> None:
    print("\n" + "=" * 60)
    print("  NaturalSentinel — MCP Server Exploration")
    print("=" * 60)
    print("  This demo connects NaturalSentinel as an MCP *client*")
    print("  to six external MCP servers.  Each server is skipped")
    print("  gracefully if its dependency is not installed.\n")

    if server:
        if server not in DEMOS:
            print(f"  Unknown server '{server}'. Choose from: {list(DEMOS)}")
            return
        label, fn = DEMOS[server]
        await fn()
    else:
        for label, fn in DEMOS.values():
            await fn()

    print("\n" + "=" * 60)
    print_registry_summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Explore external MCP servers with NaturalSentinel"
    )
    parser.add_argument(
        "--server",
        choices=list(DEMOS),
        help="Run only one server demo",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the server registry and exit",
    )
    args = parser.parse_args()

    if args.list:
        print_registry_summary()
        sys.exit(0)

    asyncio.run(main(server=args.server))
