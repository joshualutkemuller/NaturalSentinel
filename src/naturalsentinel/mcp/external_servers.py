"""
external_servers.py — MCP Client Integrations for NaturalSentinel
=================================================================

NaturalSentinel can act as an *MCP client* and connect to external MCP servers
to extend its regulatory monitoring capabilities.  This module defines
configuration helpers and async context managers for each explored server.

Servers explored
----------------
1. Filesystem  — read local regulatory PDFs / exported reports
2. Fetch       — retrieve live regulatory web pages
3. Brave Search — web-search for breaking regulatory news
4. Memory      — Anthropic's official knowledge-graph memory server
5. SQLite      — query a local compliance database
6. Time        — simple utility; injects current datetime into prompts

Each server section documents:
  • What it provides
  • Relevant tool names exposed
  • How it enhances NaturalSentinel
  • Example invocation

Usage (requires `pip install mcp`):

    import asyncio
    from naturalsentinel.mcp.external_servers import run_filesystem_demo

    asyncio.run(run_filesystem_demo("/path/to/regulatory-docs"))
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    HAS_MCP = True
except ImportError:
    HAS_MCP = False


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _require_mcp() -> None:
    if not HAS_MCP:
        raise ImportError(
            "MCP SDK not installed. Run: pip install 'naturalsentinel[mcp]'"
        )


@dataclass
class ServerResult:
    """Unified result wrapper for MCP tool calls."""

    server: str
    tool: str
    arguments: dict[str, Any]
    output: str
    success: bool
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


async def _call_tool(
    session: "ClientSession",
    tool_name: str,
    arguments: dict[str, Any],
    server_label: str,
) -> ServerResult:
    """Call an MCP tool and return a normalised ServerResult."""
    try:
        result = await session.call_tool(tool_name, arguments)
        # Extract text from the first TextContent block
        text = ""
        for block in result.content:
            if hasattr(block, "text"):
                text = block.text
                break
        return ServerResult(
            server=server_label,
            tool=tool_name,
            arguments=arguments,
            output=text,
            success=not result.isError,
        )
    except Exception as exc:
        return ServerResult(
            server=server_label,
            tool=tool_name,
            arguments=arguments,
            output="",
            success=False,
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# 1. Filesystem MCP Server
# ---------------------------------------------------------------------------
# Package : @modelcontextprotocol/server-filesystem  (Node.js)
# Install : npx -y @modelcontextprotocol/server-filesystem <allowed-dir>
#
# Relevant tools:
#   read_file        — read the contents of a file
#   list_directory   — list files in a directory
#   search_files     — glob search within the allowed directory
#
# Why it matters for NaturalSentinel:
#   Regulators publish PDFs and text dumps to shared drives. The filesystem
#   server lets NaturalSentinel ingest local copies of SEC comment letters,
#   Fed supervisory letters, or exported EDGAR filings without building a
#   custom ingestor.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def filesystem_session(allowed_directory: str):
    """Async context manager that yields an active Filesystem MCP session."""
    _require_mcp()
    params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", allowed_directory],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def run_filesystem_demo(directory: str = "/tmp") -> list[ServerResult]:
    """
    Demonstrate using the Filesystem MCP server to browse regulatory documents.

    Args:
        directory: Local directory containing regulatory documents.

    Returns:
        List of ServerResult objects from each tool call.
    """
    results: list[ServerResult] = []

    async with filesystem_session(directory) as session:
        # List available tools (logged for awareness)
        tools = await session.list_tools()
        print(f"[Filesystem] {len(tools.tools)} tools available: "
              f"{[t.name for t in tools.tools]}")

        # List directory contents
        r = await _call_tool(
            session,
            "list_directory",
            {"path": directory},
            "filesystem",
        )
        results.append(r)
        print(f"[Filesystem] list_directory → {r.output[:200]}")

        # Search for regulatory document patterns
        r = await _call_tool(
            session,
            "search_files",
            {"path": directory, "pattern": "*.pdf"},
            "filesystem",
        )
        results.append(r)
        print(f"[Filesystem] search_files (*.pdf) → {r.output[:200]}")

    return results


# ---------------------------------------------------------------------------
# 2. Fetch MCP Server
# ---------------------------------------------------------------------------
# Package : @modelcontextprotocol/server-fetch  (Node.js)
# Install : npx -y @modelcontextprotocol/server-fetch
#
# Relevant tools:
#   fetch — retrieve a URL and return its content as markdown
#
# Why it matters for NaturalSentinel:
#   NaturalSentinel's live fetchers already hit the Federal Register and BIS
#   REST APIs.  The Fetch MCP server adds general-purpose URL retrieval so
#   an LLM can autonomously decide to pull a cited rule or press release
#   mid-analysis, without requiring a pre-built fetcher for every agency.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def fetch_session():
    """Async context manager that yields an active Fetch MCP session."""
    _require_mcp()
    params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-fetch"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def run_fetch_demo(urls: list[str] | None = None) -> list[ServerResult]:
    """
    Demonstrate using the Fetch MCP server to retrieve regulatory web pages.

    Args:
        urls: List of URLs to fetch. Defaults to a public regulatory page.

    Returns:
        List of ServerResult objects.
    """
    if urls is None:
        urls = [
            "https://www.federalreserve.gov/releases/h15/",
        ]

    results: list[ServerResult] = []

    async with fetch_session() as session:
        tools = await session.list_tools()
        print(f"[Fetch] {len(tools.tools)} tools available: "
              f"{[t.name for t in tools.tools]}")

        for url in urls:
            r = await _call_tool(
                session,
                "fetch",
                {"url": url, "max_length": 2000},
                "fetch",
            )
            results.append(r)
            status = "OK" if r.success else f"ERR: {r.error}"
            print(f"[Fetch] {url} → {status} ({len(r.output)} chars)")

    return results


# ---------------------------------------------------------------------------
# 3. Brave Search MCP Server
# ---------------------------------------------------------------------------
# Package : @modelcontextprotocol/server-brave-search  (Node.js)
# Install : npx -y @modelcontextprotocol/server-brave-search
# Env var : BRAVE_API_KEY
#
# Relevant tools:
#   brave_web_search  — full web search with snippet results
#   brave_local_search — location-based search
#
# Why it matters for NaturalSentinel:
#   Regulators sometimes publish guidance via press releases or blog posts
#   before the official Federal Register notice.  Brave Search enables
#   NaturalSentinel to surface breaking regulatory developments, news
#   coverage of enforcement actions, and commentary on proposed rules.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def brave_search_session(api_key: str | None = None):
    """Async context manager that yields an active Brave Search MCP session."""
    _require_mcp()
    env = {**os.environ}
    if api_key:
        env["BRAVE_API_KEY"] = api_key
    elif "BRAVE_API_KEY" not in env:
        raise EnvironmentError(
            "BRAVE_API_KEY not set. Export it or pass api_key= to brave_search_session()."
        )
    params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-brave-search"],
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def run_brave_search_demo(
    queries: list[str] | None = None,
    api_key: str | None = None,
) -> list[ServerResult]:
    """
    Demonstrate regulatory news discovery via Brave Search.

    Args:
        queries: Search queries to run.
        api_key: Brave API key (falls back to BRAVE_API_KEY env var).

    Returns:
        List of ServerResult objects.
    """
    if queries is None:
        queries = [
            "SEC enforcement action 2025",
            "CFPB mortgage rule proposed",
            "Federal Reserve Basel III capital requirements",
        ]

    results: list[ServerResult] = []

    async with brave_search_session(api_key) as session:
        tools = await session.list_tools()
        print(f"[Brave Search] {len(tools.tools)} tools available: "
              f"{[t.name for t in tools.tools]}")

        for query in queries:
            r = await _call_tool(
                session,
                "brave_web_search",
                {"query": query, "count": 5},
                "brave-search",
            )
            results.append(r)
            status = "OK" if r.success else f"ERR: {r.error}"
            print(f"[Brave Search] '{query}' → {status}")
            if r.success:
                # Pretty-print first result title if JSON parseable
                try:
                    data = json.loads(r.output)
                    first = data.get("results", [{}])[0]
                    print(f"  Top result: {first.get('title', 'N/A')}")
                except (json.JSONDecodeError, IndexError):
                    print(f"  Output snippet: {r.output[:120]}")

    return results


# ---------------------------------------------------------------------------
# 4. Memory MCP Server  (Anthropic's official knowledge-graph server)
# ---------------------------------------------------------------------------
# Package : @modelcontextprotocol/server-memory  (Node.js)
# Install : npx -y @modelcontextprotocol/server-memory
#
# Relevant tools:
#   create_entities    — add nodes to the knowledge graph
#   create_relations   — link entities
#   add_observations   — append facts to existing entities
#   search_nodes       — semantic search over the graph
#   read_graph         — return the entire graph
#   delete_entities    — remove stale nodes
#
# Why it matters for NaturalSentinel:
#   NaturalSentinel ships its own memory.py (SQLite-backed, episodic +
#   entity + precedent).  The official Memory MCP server provides an
#   alternative knowledge-graph backend that any MCP-compatible client can
#   read — not just NaturalSentinel.  This is valuable when multiple tools
#   (Claude Desktop, Cursor, an internal dashboard) need to share regulatory
#   entity knowledge.  The two memory systems can be used in parallel or
#   as a migration path.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def memory_mcp_session():
    """Async context manager that yields an active Memory MCP session."""
    _require_mcp()
    params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-memory"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def run_memory_mcp_demo() -> list[ServerResult]:
    """
    Demonstrate storing and retrieving regulatory entities via the Memory MCP server.

    Contrast with NaturalSentinel's built-in memory.py:
      • memory.py  — SQLite-backed, structured episode/entity/precedent types
      • Memory MCP — portable knowledge graph, readable by any MCP client

    Returns:
        List of ServerResult objects.
    """
    results: list[ServerResult] = []

    async with memory_mcp_session() as session:
        tools = await session.list_tools()
        print(f"[Memory MCP] {len(tools.tools)} tools available: "
              f"{[t.name for t in tools.tools]}")

        # Create regulatory entities in the shared graph
        entities_payload = {
            "entities": [
                {
                    "name": "SEC Rule 10b-5",
                    "entityType": "Regulation",
                    "observations": [
                        "Anti-fraud provision under the Securities Exchange Act of 1934",
                        "Prohibits material misstatements in connection with securities transactions",
                        "Enforcement actions have increased 23% in 2025",
                    ],
                },
                {
                    "name": "CFPB",
                    "entityType": "RegulatoryAgency",
                    "observations": [
                        "Consumer Financial Protection Bureau",
                        "Oversees consumer financial products including mortgages, credit cards, and student loans",
                        "Proposed new open banking rule in 2024",
                    ],
                },
            ]
        }
        r = await _call_tool(session, "create_entities", entities_payload, "memory-mcp")
        results.append(r)
        print(f"[Memory MCP] create_entities → {'OK' if r.success else r.error}")

        # Link the entities
        relations_payload = {
            "relations": [
                {
                    "from": "CFPB",
                    "to": "SEC Rule 10b-5",
                    "relationType": "coordinates_enforcement_with",
                }
            ]
        }
        r = await _call_tool(session, "create_relations", relations_payload, "memory-mcp")
        results.append(r)
        print(f"[Memory MCP] create_relations → {'OK' if r.success else r.error}")

        # Search the graph
        r = await _call_tool(
            session,
            "search_nodes",
            {"query": "anti-fraud securities"},
            "memory-mcp",
        )
        results.append(r)
        print(f"[Memory MCP] search_nodes → {r.output[:200]}")

    return results


# ---------------------------------------------------------------------------
# 5. SQLite MCP Server
# ---------------------------------------------------------------------------
# Package : mcp-server-sqlite  (Python, pip install mcp-server-sqlite)
# Run     : python -m mcp_server_sqlite --db-path compliance.db
#
# Relevant tools:
#   read_query   — execute a SELECT statement
#   write_query  — execute INSERT/UPDATE/DELETE
#   list_tables  — enumerate schema
#   describe_table — inspect column types
#
# Why it matters for NaturalSentinel:
#   A compliance team may already store their tracking data (open findings,
#   remediation deadlines, business-line ownership) in SQLite or Postgres.
#   The SQLite MCP server lets NaturalSentinel query live compliance records
#   to cross-reference impact assessments against existing obligations —
#   without ETL pipelines.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def sqlite_session(db_path: str):
    """Async context manager that yields an active SQLite MCP session."""
    _require_mcp()
    params = StdioServerParameters(
        command="python",
        args=["-m", "mcp_server_sqlite", "--db-path", db_path],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def run_sqlite_demo(db_path: str = "/tmp/compliance_demo.db") -> list[ServerResult]:
    """
    Demonstrate querying a compliance database via the SQLite MCP server.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        List of ServerResult objects.
    """
    import sqlite3

    # Seed a demo database
    con = sqlite3.connect(db_path)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS compliance_findings (
            id          INTEGER PRIMARY KEY,
            domain      TEXT NOT NULL,
            title       TEXT NOT NULL,
            severity    TEXT NOT NULL,
            deadline    TEXT,
            status      TEXT DEFAULT 'open'
        );
        INSERT OR IGNORE INTO compliance_findings VALUES
            (1, 'sec',  'Rule 15c3-3 net capital shortfall',      'high',     '2025-09-30', 'open'),
            (2, 'cfpb', 'HMDA reporting gap Q1 2025',             'medium',   '2025-06-15', 'remediated'),
            (3, 'fed',  'Basel III leverage ratio below threshold','critical', '2025-12-31', 'open');
    """)
    con.close()

    results: list[ServerResult] = []

    async with sqlite_session(db_path) as session:
        tools = await session.list_tools()
        print(f"[SQLite MCP] {len(tools.tools)} tools available: "
              f"{[t.name for t in tools.tools]}")

        # List tables
        r = await _call_tool(session, "list_tables", {}, "sqlite-mcp")
        results.append(r)
        print(f"[SQLite MCP] list_tables → {r.output}")

        # Query open high/critical findings
        r = await _call_tool(
            session,
            "read_query",
            {
                "query": (
                    "SELECT domain, title, severity, deadline "
                    "FROM compliance_findings "
                    "WHERE status = 'open' AND severity IN ('high', 'critical') "
                    "ORDER BY deadline;"
                )
            },
            "sqlite-mcp",
        )
        results.append(r)
        print(f"[SQLite MCP] open critical/high findings → {r.output}")

    return results


# ---------------------------------------------------------------------------
# 6. Time MCP Server
# ---------------------------------------------------------------------------
# Package : mcp-server-time  (Python, pip install mcp-server-time)
# Run     : python -m mcp_server_time
#
# Relevant tools:
#   get_current_time  — return current UTC and local time with timezone info
#   convert_time      — convert between timezones
#
# Why it matters for NaturalSentinel:
#   Compliance deadlines are timezone-sensitive (a rule may specify Eastern
#   Time for a comment-period close).  The Time server gives the LLM a
#   reliable, injected "now" timestamp and conversion capability so deadline
#   calculations are accurate regardless of where the server is running.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def time_session():
    """Async context manager that yields an active Time MCP session."""
    _require_mcp()
    params = StdioServerParameters(
        command="python",
        args=["-m", "mcp_server_time"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def run_time_demo() -> list[ServerResult]:
    """
    Demonstrate timezone-aware deadline handling via the Time MCP server.

    Returns:
        List of ServerResult objects.
    """
    results: list[ServerResult] = []

    async with time_session() as session:
        tools = await session.list_tools()
        print(f"[Time MCP] {len(tools.tools)} tools available: "
              f"{[t.name for t in tools.tools]}")

        # Get current time in UTC and Eastern (SEC/CFPB reference timezone)
        r = await _call_tool(
            session,
            "get_current_time",
            {"timezone": "UTC"},
            "time-mcp",
        )
        results.append(r)
        print(f"[Time MCP] UTC now → {r.output}")

        r = await _call_tool(
            session,
            "convert_time",
            {
                "source_timezone": "UTC",
                "time": "23:59",
                "target_timezone": "America/New_York",
            },
            "time-mcp",
        )
        results.append(r)
        print(f"[Time MCP] 23:59 UTC → Eastern → {r.output}")

    return results


# ---------------------------------------------------------------------------
# Comparison summary
# ---------------------------------------------------------------------------


SERVER_REGISTRY: dict[str, dict[str, str]] = {
    "filesystem": {
        "package": "@modelcontextprotocol/server-filesystem",
        "runtime": "node",
        "install": "npx -y @modelcontextprotocol/server-filesystem <dir>",
        "use_case": "Ingest local regulatory PDFs and exported filings",
        "key_tools": "read_file, list_directory, search_files",
    },
    "fetch": {
        "package": "@modelcontextprotocol/server-fetch",
        "runtime": "node",
        "install": "npx -y @modelcontextprotocol/server-fetch",
        "use_case": "Retrieve live regulatory web pages as markdown",
        "key_tools": "fetch",
    },
    "brave-search": {
        "package": "@modelcontextprotocol/server-brave-search",
        "runtime": "node",
        "install": "npx -y @modelcontextprotocol/server-brave-search",
        "use_case": "Discover breaking regulatory news before Federal Register publication",
        "key_tools": "brave_web_search, brave_local_search",
        "env_required": "BRAVE_API_KEY",
    },
    "memory": {
        "package": "@modelcontextprotocol/server-memory",
        "runtime": "node",
        "install": "npx -y @modelcontextprotocol/server-memory",
        "use_case": "Portable knowledge graph shared across all MCP clients",
        "key_tools": "create_entities, create_relations, search_nodes, read_graph",
    },
    "sqlite": {
        "package": "mcp-server-sqlite",
        "runtime": "python",
        "install": "pip install mcp-server-sqlite",
        "use_case": "Query existing compliance databases for cross-referencing",
        "key_tools": "read_query, write_query, list_tables, describe_table",
    },
    "time": {
        "package": "mcp-server-time",
        "runtime": "python",
        "install": "pip install mcp-server-time",
        "use_case": "Timezone-aware compliance deadline calculation",
        "key_tools": "get_current_time, convert_time",
    },
}


def print_registry_summary() -> None:
    """Print a formatted table of all explored MCP servers."""
    print("\n" + "=" * 80)
    print("  NaturalSentinel — MCP Server Exploration Registry")
    print("=" * 80)
    for name, info in SERVER_REGISTRY.items():
        print(f"\n  [{name.upper()}]")
        print(f"    Package   : {info['package']}")
        print(f"    Runtime   : {info['runtime']}")
        print(f"    Install   : {info['install']}")
        print(f"    Use case  : {info['use_case']}")
        print(f"    Key tools : {info['key_tools']}")
        if "env_required" in info:
            print(f"    Env var   : {info['env_required']}")
    print("\n" + "=" * 80 + "\n")
