"""
mcp_server.py — Model Context Protocol Server for the Regulatory Monitor
=========================================================================

Exposes the regulatory monitor agent as a standardized MCP server so that
any MCP-compatible client (Claude Desktop, Claude Code, Cursor, Zed, custom
agents) can interact with it.

MCP Concepts Implemented:
─────────────────────────
TOOLS     — Functions the LLM can invoke (analyze a filing, run a scan, give feedback)
RESOURCES — Read-only data the LLM can pull in as context (filing history, memory stats)
PROMPTS   — Pre-built prompt templates for common workflows

Run with:
    python mcp_server.py                        # stdio transport (default, for Claude Desktop)
    python mcp_server.py --transport sse         # SSE transport (for web clients)
    python mcp_server.py --transport streamable  # Streamable HTTP (newest MCP transport)

Configure in Claude Desktop's claude_desktop_config.json:
{
  "mcpServers": {
    "regulatory-monitor": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
"""

import json
import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# MCP SDK import with graceful fallback
# ---------------------------------------------------------------------------

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Prompt,
        PromptArgument,
        PromptMessage,
        Resource,
        ResourceTemplate,
        TextContent,
        Tool,
    )

    HAS_MCP = True
except ImportError:
    HAS_MCP = False

# Local imports
from app.naturalsentinel.cli import build_provider, create_runtime
from app.naturalsentinel.fetchers import DOMAIN_BUSINESS_LINES
from app.naturalsentinel.mcp import openviking as ov_bridge
from app.naturalsentinel.memory.store import MemoryStore
from app.naturalsentinel.memory.types import MemoryType
from app.naturalsentinel.models import RegulatoryDomain, RegulatoryFiling
from app.naturalsentinel.providers.base import ModelProvider
from app.naturalsentinel.utils.serialization import enum_serializer

logger = logging.getLogger("SentinelMCP")

# ---------------------------------------------------------------------------
# Shared state — initialized once when server starts
# ---------------------------------------------------------------------------

_memory: MemoryStore | None = None
_runtime = None


def _get_memory() -> MemoryStore:
    global _memory
    if _memory is None:
        db_path = os.getenv("SENTINEL_MEMORY_DB", "naturalsentinel_memory.db")
        _memory = MemoryStore(db_path)
    return _memory


def _get_runtime():
    global _runtime
    if _runtime is None:
        provider_name = os.getenv("SENTINEL_PROVIDER", "mock")
        model = os.getenv("SENTINEL_MODEL")
        try:
            provider = _build_provider(provider_name, model)
        except ImportError:
            logger.warning(
                "Provider %s unavailable; falling back to mock provider", provider_name
            )
            provider = _build_provider("mock")
        _runtime = create_runtime(
            provider,
            memory=_get_memory(),
            state_path=os.getenv("SENTINEL_STATE", "monitor_state.json"),
        )
    return _runtime


def _build_provider(name: str, model: str | None = None) -> ModelProvider:
    return build_provider(name, model)


# ═══════════════════════════════════════════════════════════════════════════
# MCP SERVER DEFINITION
# ═══════════════════════════════════════════════════════════════════════════


def create_mcp_server() -> "Server":
    """Build and configure the MCP server with all tools, resources, and prompts."""

    if not HAS_MCP:
        raise ImportError(
            "MCP SDK not installed. Run: pip install mcp\n"
            "See: https://modelcontextprotocol.io/quickstart/server"
        )

    server = Server("regulatory-monitor")

    # ───────────────────────────────────────────────────────────────────
    # TOOLS — Functions the LLM can call
    # ───────────────────────────────────────────────────────────────────

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="scan_regulatory_filings",
                description=(
                    "Run a regulatory monitoring scan across specified agencies. "
                    "Fetches new filings, analyzes each with AI, and returns "
                    "structured impact assessments. Results are stored in memory."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "domains": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["sec", "cfpb", "fed", "fda", "epa", "ustr"],
                            },
                            "description": "Regulatory agencies to scan. Omit for all.",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Look-back window in days (default: 30)",
                            "default": 30,
                        },
                    },
                },
            ),
            Tool(
                name="analyze_filing_text",
                description=(
                    "Analyze a specific piece of regulatory text provided by the user. "
                    "Returns a structured impact assessment with severity, affected "
                    "business lines, action items, and deadlines."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Title of the filing or document",
                        },
                        "text": {
                            "type": "string",
                            "description": "The regulatory text to analyze",
                        },
                        "domain": {
                            "type": "string",
                            "enum": ["sec", "cfpb", "fed", "fda", "epa", "ustr"],
                            "description": "Regulatory domain",
                        },
                    },
                    "required": ["title", "text", "domain"],
                },
            ),
            Tool(
                name="recall_memory",
                description=(
                    "Search the agent's persistent memory for relevant past analyses, "
                    "entity knowledge, or correction precedents. Use this to find "
                    "how similar filings were handled before."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "memory_type": {
                            "type": "string",
                            "enum": ["episodic", "entity", "precedent"],
                            "description": "Filter by memory type (optional)",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results (default: 5)",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="provide_feedback",
                description=(
                    "Record a correction or feedback on a past analysis. The agent "
                    "will learn from this feedback and apply it to future analyses. "
                    "For example: severity was wrong, a business line was missed, "
                    "a deadline was incorrect."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filing_id": {
                            "type": "string",
                            "description": "The filing ID to correct",
                        },
                        "field": {
                            "type": "string",
                            "description": "Which field to correct (severity, affected_business_lines, compliance_deadline, etc.)",
                        },
                        "old_value": {
                            "type": "string",
                            "description": "The current/wrong value",
                        },
                        "new_value": {
                            "type": "string",
                            "description": "The correct value",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Why this correction is needed",
                        },
                    },
                    "required": ["filing_id", "field", "old_value", "new_value"],
                },
            ),
            Tool(
                name="get_entity_relations",
                description=(
                    "Explore the knowledge graph of relationships between regulations, "
                    "agencies, and business lines. Shows how entities are connected "
                    "based on all past analyses."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity": {
                            "type": "string",
                            "description": "Entity name (regulation, agency, business line)",
                        },
                    },
                    "required": ["entity"],
                },
            ),
            Tool(
                name="get_memory_stats",
                description="Get statistics about the agent's memory store — how many filings analyzed, feedback recorded, entities tracked.",
                inputSchema={"type": "object", "properties": {}},
            ),
            # ── OpenViking context database tools ──────────────────────────
            Tool(
                name="openviking_search",
                description=(
                    "Semantic search across the OpenViking context store. "
                    "Returns the most relevant resources for a natural-language query. "
                    "Use to find regulatory documents, prior analyses, or any ingested content."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural-language search query",
                        },
                        "target_uri": {
                            "type": "string",
                            "description": "Restrict search to this viking:// URI subtree (optional)",
                            "default": "",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results to return (default: 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="openviking_read",
                description="Read the full content of a resource at a viking:// URI.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "uri": {
                            "type": "string",
                            "description": "viking:// URI of the resource",
                        },
                    },
                    "required": ["uri"],
                },
            ),
            Tool(
                name="openviking_list",
                description="List resources under a viking:// URI (directory listing).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "uri": {
                            "type": "string",
                            "description": "viking:// URI to list (default: viking://)",
                            "default": "viking://",
                        },
                    },
                },
            ),
            Tool(
                name="openviking_add_resource",
                description="Ingest a URL or local file path into the OpenViking context store.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "URL or local file path to ingest",
                        },
                        "wait": {
                            "type": "boolean",
                            "description": "Block until processing is complete (default: true)",
                            "default": True,
                        },
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="openviking_grep",
                description="Regex content search within resources under a viking:// URI.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "uri": {
                            "type": "string",
                            "description": "viking:// URI subtree to search",
                        },
                        "pattern": {"type": "string", "description": "Regex pattern"},
                        "case_insensitive": {"type": "boolean", "default": False},
                    },
                    "required": ["uri", "pattern"],
                },
            ),
            Tool(
                name="openviking_glob",
                description="Path-pattern match (glob) within the OpenViking filesystem.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Glob pattern e.g. **/*.md",
                        },
                        "uri": {
                            "type": "string",
                            "description": "Root URI (default: viking://)",
                            "default": "viking://",
                        },
                    },
                    "required": ["pattern"],
                },
            ),
            Tool(
                name="openviking_memory_commit",
                description="Commit a session to long-term memory in OpenViking.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "OpenViking session ID to commit",
                        },
                    },
                    "required": ["session_id"],
                },
            ),
            # ── State-level monitoring tools ────────────────────────────────
            Tool(
                name="scan_state_filings",
                description=(
                    "Scan US state-level regulatory filings filtered by industry sector "
                    "and/or state. Sources: Open States (legislative bills), state agency "
                    "RSS feeds, NASAA (securities), NAIC (insurance), CSBS (banking). "
                    "Returns filings grouped by state → sector."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "state_codes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                'Two-letter state codes to include, e.g. ["CA", "NY"]. '
                                'Pass ["all"] or omit to scan all registered states.'
                            ),
                        },
                        "sectors": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "financial_services",
                                    "healthcare",
                                    "insurance",
                                    "energy_utilities",
                                    "real_estate",
                                    "technology",
                                    "manufacturing",
                                    "transportation",
                                ],
                            },
                            "description": "Industry sectors to filter by. Omit for all sectors.",
                        },
                        "since_days": {
                            "type": "integer",
                            "description": "Look-back window in days (default: 7)",
                            "default": 7,
                        },
                        "include_federal": {
                            "type": "boolean",
                            "description": "Also include matching federal filings (default: false)",
                            "default": False,
                        },
                    },
                },
            ),
            Tool(
                name="get_sector_regulatory_calendar",
                description=(
                    "Return upcoming compliance deadlines and effective dates extracted "
                    "from ingested state (and optionally federal) filings for a given "
                    "sector. Queries stored filings in memory sorted by date."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sector": {
                            "type": "string",
                            "enum": [
                                "financial_services",
                                "healthcare",
                                "insurance",
                                "energy_utilities",
                                "real_estate",
                                "technology",
                                "manufacturing",
                                "transportation",
                            ],
                            "description": "Industry sector to query",
                        },
                        "state_codes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Limit to these states. Omit for all.",
                        },
                        "months_ahead": {
                            "type": "integer",
                            "description": "How many months forward to look (default: 3)",
                            "default": 3,
                        },
                    },
                    "required": ["sector"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            result = _handle_tool(name, arguments)
            return [TextContent(type="text", text=result)]
        except Exception as e:
            logger.exception("Tool error: %s", name)
            return [TextContent(type="text", text=f"Error: {e}")]

    def _handle_tool(name: str, args: dict) -> str:
        mem = _get_memory()

        if name == "scan_regulatory_filings":
            runtime = _get_runtime()
            scan_params = {"since_days": args.get("days", 30)}
            if args.get("domains"):
                scan_params["domains"] = args["domains"]
            Path(runtime.state_path).write_text(json.dumps({"seen_ids": []}))
            result = runtime.execute_skill("scan_cycle", scan_params)
            if not result.success:
                raise RuntimeError(result.error)
            output = json.loads(
                json.dumps(result.data["results"], default=enum_serializer)
            )
            return json.dumps(
                {
                    "status": "success",
                    "filings_analyzed": len(output),
                    "results": output,
                },
                indent=2,
            )

        elif name == "analyze_filing_text":
            import hashlib as _hashlib

            runtime = _get_runtime()
            fid = (
                f"CUSTOM-{_hashlib.sha256(args['text'][:100].encode()).hexdigest()[:8]}"
            )
            filing = RegulatoryFiling(
                id=fid,
                title=args["title"],
                domain=RegulatoryDomain(args["domain"]),
                source_url="user-provided",
                published_date=datetime.utcnow().strftime("%Y-%m-%d"),
                raw_text=args["text"],
            )
            filing_data = json.loads(
                json.dumps(filing.__dict__, default=enum_serializer)
            )
            context_result = runtime.execute_skill(
                "build_context",
                {"domain": filing.domain.value, "filing_text": filing.raw_text},
            )
            result = runtime.execute_skill(
                "analyze_filing",
                {
                    "filing": filing_data,
                    "memory_context": context_result.data
                    if context_result.success
                    else "",
                },
            )
            if not result.success:
                raise RuntimeError(result.error)
            payload = {"filing": filing_data, "impact": result.data}
            runtime.execute_skill(
                "store_memory",
                {"filing_id": fid, "filing": filing_data, "impact": result.data},
            )
            return json.dumps(
                json.loads(json.dumps(payload, default=enum_serializer)), indent=2
            )

        elif name == "recall_memory":
            runtime = _get_runtime()
            result = runtime.execute_skill("recall_memory", args)
            if not result.success:
                raise RuntimeError(result.error)
            return json.dumps(result.data, indent=2)

        elif name == "provide_feedback":
            runtime = _get_runtime()
            result = runtime.execute_skill("record_feedback", args)
            if not result.success:
                raise RuntimeError(result.error)
            return json.dumps(
                {
                    "status": "recorded",
                    "message": f"Feedback recorded for {args['filing_id']}.{args['field']}. "
                    f"This correction will be used in future analyses.",
                    "result": result.data,
                }
            )

        elif name == "get_entity_relations":
            relations = mem.get_related_entities(args["entity"])
            return json.dumps(relations, indent=2, default=str)

        elif name == "get_memory_stats":
            return json.dumps(mem.stats(), indent=2)

        # ── OpenViking tools ────────────────────────────────────────────
        elif name == "openviking_search":
            result = ov_bridge.ov_search(
                query=args["query"],
                target_uri=args.get("target_uri", ""),
                limit=args.get("limit", 10),
            )
            return json.dumps(result, indent=2, default=str)

        elif name == "openviking_read":
            return ov_bridge.ov_read(args["uri"])

        elif name == "openviking_list":
            result = ov_bridge.ov_list(args.get("uri", "viking://"))
            return json.dumps(result, indent=2, default=str)

        elif name == "openviking_add_resource":
            result = ov_bridge.ov_add_resource(
                path=args["path"], wait=args.get("wait", True)
            )
            return json.dumps(result, indent=2, default=str)

        elif name == "openviking_grep":
            result = ov_bridge.ov_grep(
                uri=args["uri"],
                pattern=args["pattern"],
                case_insensitive=args.get("case_insensitive", False),
            )
            return json.dumps(result, indent=2, default=str)

        elif name == "openviking_glob":
            result = ov_bridge.ov_glob(
                pattern=args["pattern"], uri=args.get("uri", "viking://")
            )
            return json.dumps(result, indent=2, default=str)

        elif name == "openviking_memory_commit":
            result = ov_bridge.ov_commit_session(args["session_id"])
            return json.dumps(result, indent=2, default=str)

        elif name == "scan_state_filings":
            from app.naturalsentinel.fetchers.base import fetch_filings
            from app.naturalsentinel.models import (
                IndustrySector,
                Jurisdiction,
                StateCode,
            )

            raw_states = args.get("state_codes") or []
            if raw_states == ["all"]:
                raw_states = []
            state_codes = []
            for sc in raw_states:
                try:
                    state_codes.append(StateCode(sc))
                except ValueError:
                    pass

            raw_sectors = args.get("sectors") or []
            sectors = []
            for s in raw_sectors:
                try:
                    sectors.append(IndustrySector(s))
                except ValueError:
                    pass

            since_days = int(args.get("since_days", 7))
            include_federal = bool(args.get("include_federal", False))
            jurisdiction = None if include_federal else Jurisdiction.STATE

            filings = fetch_filings(
                sectors=sectors or None,
                state_codes=state_codes or None,
                jurisdiction=jurisdiction,
                since_days=since_days,
                live=True,
                fetch_full_text=False,
            )

            # Group by state → sector
            grouped: dict[str, dict[str, list[dict]]] = {}
            for f in filings:
                key = f.state_code.value if f.state_code else f.jurisdiction.value
                for sector in f.industry_sectors or [f.domain.value]:
                    grouped.setdefault(key, {}).setdefault(sector, []).append(
                        {
                            "id": f.id,
                            "title": f.title,
                            "domain": f.domain.value,
                            "source_url": f.source_url,
                            "published_date": f.published_date,
                            "change_type": f.change_type.value,
                            "jurisdiction": f.jurisdiction.value,
                        }
                    )

            return json.dumps(
                {
                    "total": len(filings),
                    "since_days": since_days,
                    "grouped": grouped,
                },
                indent=2,
                default=str,
            )

        elif name == "get_sector_regulatory_calendar":
            sector = args.get("sector", "")
            state_filter = set(args.get("state_codes") or [])
            months_ahead = int(args.get("months_ahead", 3))

            # Fetch recent + upcoming filings from live sources for the sector
            from app.naturalsentinel.fetchers.base import fetch_filings
            from app.naturalsentinel.models import (
                IndustrySector,
                Jurisdiction,
                StateCode,
            )

            try:
                sector_enum = IndustrySector(sector)
            except ValueError:
                return json.dumps({"error": f"Unknown sector: {sector}"})

            state_codes = []
            for sc in state_filter:
                try:
                    state_codes.append(StateCode(sc))
                except ValueError:
                    pass

            # Use a wider look-back to capture recently published effective dates
            since_days = months_ahead * 31
            filings = fetch_filings(
                sectors=[sector_enum],
                state_codes=state_codes or None,
                jurisdiction=Jurisdiction.STATE,
                since_days=since_days,
                live=True,
                fetch_full_text=False,
            )

            horizon = datetime.now(UTC) + timedelta(days=months_ahead * 31)
            today_str = datetime.now(UTC).strftime("%Y-%m-%d")
            horizon_str = horizon.strftime("%Y-%m-%d")

            # Extract filings with known dates and sort chronologically
            calendar_entries = []
            for f in filings:
                if f.published_date >= today_str:
                    calendar_entries.append(
                        {
                            "date": f.published_date,
                            "title": f.title,
                            "state": f.state_code.value if f.state_code else "federal",
                            "change_type": f.change_type.value,
                            "source_url": f.source_url,
                            "sectors": f.industry_sectors,
                        }
                    )

            calendar_entries.sort(key=lambda x: x["date"])

            return json.dumps(
                {
                    "sector": sector,
                    "state_filter": list(state_filter) or "all",
                    "horizon": horizon_str,
                    "total": len(calendar_entries),
                    "calendar": calendar_entries,
                },
                indent=2,
                default=str,
            )

        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    # ───────────────────────────────────────────────────────────────────
    # RESOURCES — Read-only data the LLM can pull in
    # ───────────────────────────────────────────────────────────────────

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="naturalsentinel://filings/recent",
                name="Recent Filing Analyses",
                description="The most recent regulatory filing analyses from memory",
                mimeType="application/json",
            ),
            Resource(
                uri="naturalsentinel://memory/stats",
                name="Memory Statistics",
                description="Current state of the agent's memory system",
                mimeType="application/json",
            ),
            Resource(
                uri="naturalsentinel://config/domains",
                name="Monitored Domains",
                description="List of regulatory domains and their associated business lines",
                mimeType="application/json",
            ),
        ]

    @server.list_resource_templates()
    async def list_resource_templates() -> list[ResourceTemplate]:
        return [
            ResourceTemplate(
                uriTemplate="naturalsentinel://filings/domain/{domain}",
                name="Filings by Domain",
                description="Filing history for a specific regulatory domain (sec, cfpb, fed, fda, epa, ustr)",
            ),
            ResourceTemplate(
                uriTemplate="naturalsentinel://entity/{name}",
                name="Entity Knowledge",
                description="Everything the agent knows about a specific regulation, agency, or business line",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        mem = _get_memory()

        if uri == "naturalsentinel://filings/recent":
            records = mem.get_filing_history(limit=10)
            return json.dumps([r.content for r in records], indent=2)

        elif uri == "naturalsentinel://memory/stats":
            return json.dumps(mem.stats(), indent=2)

        elif uri == "naturalsentinel://config/domains":
            return json.dumps(
                {
                    "domains": [d.value for d in RegulatoryDomain],
                    "business_lines": DOMAIN_BUSINESS_LINES,
                },
                indent=2,
            )

        elif uri.startswith("naturalsentinel://filings/domain/"):
            domain = uri.split("/")[-1]
            records = mem.get_filing_history(domain=domain, limit=20)
            return json.dumps([r.content for r in records], indent=2)

        elif uri.startswith("naturalsentinel://entity/"):
            entity = uri.split("/", 3)[-1]
            relations = mem.get_related_entities(entity)
            memories = mem.recall(entity, top_k=5, memory_type=MemoryType.ENTITY)
            return json.dumps(
                {
                    "entity": entity,
                    "relations": relations,
                    "memories": [
                        {"key": m.key, "content": m.content} for m in memories
                    ],
                },
                indent=2,
                default=str,
            )

        return json.dumps({"error": f"Unknown resource: {uri}"})

    # ───────────────────────────────────────────────────────────────────
    # PROMPTS — Pre-built templates for common workflows
    # ───────────────────────────────────────────────────────────────────

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name="regulatory_briefing",
                description=(
                    "Generate a concise executive briefing of recent regulatory "
                    "changes across all monitored domains"
                ),
                arguments=[
                    PromptArgument(
                        name="audience",
                        description="Target audience (board, compliance_team, risk_committee, general_counsel)",
                        required=False,
                    ),
                ],
            ),
            Prompt(
                name="impact_deep_dive",
                description="Deep-dive analysis of a specific filing's impact on the organization",
                arguments=[
                    PromptArgument(
                        name="filing_id",
                        description="The filing ID to analyze in depth",
                        required=True,
                    ),
                ],
            ),
            Prompt(
                name="compliance_gap_analysis",
                description="Identify compliance gaps across all recent filings for a specific business line",
                arguments=[
                    PromptArgument(
                        name="business_line",
                        description="The business line to assess (e.g. 'Consumer Lending', 'Digital Assets')",
                        required=True,
                    ),
                ],
            ),
        ]

    @server.get_prompt()
    async def get_prompt(
        name: str, arguments: dict | None = None
    ) -> list[PromptMessage]:
        args = arguments or {}
        mem = _get_memory()

        if name == "regulatory_briefing":
            audience = args.get("audience", "executive leadership")
            recent = mem.get_filing_history(limit=10)
            context = (
                "\n".join(
                    [
                        f"- {r.content.get('filing', {}).get('title', '?')} "
                        f"(severity: {r.content.get('impact', {}).get('severity', '?')})"
                        for r in recent
                    ]
                )
                or "No filings in memory yet. Run a scan first."
            )

            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Generate a concise regulatory briefing for {audience}.\n\n"
                            f"Recent filings in the system:\n{context}\n\n"
                            f"Use the scan_regulatory_filings tool to get the latest data, "
                            f"then produce a structured briefing with:\n"
                            f"1. Executive summary (3-4 sentences)\n"
                            f"2. Critical items requiring immediate attention\n"
                            f"3. Upcoming deadlines\n"
                            f"4. Recommended actions by department"
                        ),
                    ),
                )
            ]

        elif name == "impact_deep_dive":
            filing_id = args.get("filing_id", "")
            record = mem.get(f"episodic:{filing_id}")
            context = (
                json.dumps(record.content, indent=2)
                if record
                else "Filing not found in memory."
            )

            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Perform a deep-dive impact analysis for filing {filing_id}.\n\n"
                            f"Filing data:\n{context}\n\n"
                            f"Use recall_memory and get_entity_relations to find related "
                            f"filings and entity connections. Then provide:\n"
                            f"1. Detailed regulatory impact chain\n"
                            f"2. Cross-references to related active regulations\n"
                            f"3. Department-by-department action plan with timelines\n"
                            f"4. Estimated compliance cost range\n"
                            f"5. Risk scenarios if action is delayed"
                        ),
                    ),
                )
            ]

        elif name == "compliance_gap_analysis":
            biz_line = args.get("business_line", "")
            related = mem.recall(biz_line, top_k=10, memory_type=MemoryType.EPISODIC)
            context = (
                "\n".join(
                    [
                        f"- {r.key}: {r.content.get('impact', {}).get('severity', '?')}"
                        for r in related
                    ]
                )
                or "No related filings found."
            )

            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Perform a compliance gap analysis for the '{biz_line}' business line.\n\n"
                            f"Related filings:\n{context}\n\n"
                            f"Use recall_memory to search for all relevant filings and precedents. "
                            f"Then produce:\n"
                            f"1. Summary of all regulatory requirements affecting this business line\n"
                            f"2. Current compliance posture (based on action items)\n"
                            f"3. Identified gaps\n"
                            f"4. Prioritized remediation roadmap\n"
                            f"5. Cross-regulatory dependencies"
                        ),
                    ),
                )
            ]

        return [
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=f"Unknown prompt: {name}"),
            )
        ]

    return server


# ═══════════════════════════════════════════════════════════════════════════
# STANDALONE MODE — When MCP SDK is not available, expose the same
# capabilities as a simple JSON-RPC style interface over stdin/stdout
# ═══════════════════════════════════════════════════════════════════════════


class StandaloneServer:
    """
    A lightweight MCP-like server that works without the MCP SDK.
    Reads JSON requests from stdin, writes JSON responses to stdout.
    Implements the same tool/resource/prompt interface.

    This allows the agent to be integrated with custom tooling,
    shell scripts, or any process that can pipe JSON.
    """

    def __init__(self):
        global _runtime
        _runtime = None
        self.memory = _get_memory()
        self.runtime = _get_runtime()
        self.tools = {
            "scan_regulatory_filings": self._scan,
            "recall_memory": self._recall,
            "provide_feedback": self._feedback,
            "get_entity_relations": self._relations,
            "get_memory_stats": self._stats,
            # OpenViking context database
            "openviking_search": self._ov_search,
            "openviking_read": self._ov_read,
            "openviking_list": self._ov_list,
            "openviking_add_resource": self._ov_add_resource,
            "openviking_grep": self._ov_grep,
            "openviking_glob": self._ov_glob,
            "openviking_memory_commit": self._ov_memory_commit,
            # State-level monitoring
            "scan_state_filings": self._scan_state_filings,
            "get_sector_regulatory_calendar": self._get_sector_regulatory_calendar,
        }

    def handle_request(self, request: dict) -> dict:
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "tools/list":
            return {"tools": list(self.tools.keys())}
        elif method == "tools/call":
            tool_name = params.get("name", "")
            args = params.get("arguments", {})
            if tool_name in self.tools:
                try:
                    return {"result": self.tools[tool_name](args)}
                except Exception as exc:
                    return {"error": f"{type(exc).__name__}: {exc}"}
            return {"error": f"Unknown tool: {tool_name}"}
        elif method == "resources/list":
            return {
                "resources": [
                    "naturalsentinel://filings/recent",
                    "naturalsentinel://memory/stats",
                    "naturalsentinel://config/domains",
                ]
            }
        elif method == "resources/read":
            uri = params.get("uri", "")
            return {"result": self._read_resource(uri)}
        else:
            return {"error": f"Unknown method: {method}"}

    def _scan(self, args: dict) -> dict:
        scan_params = {"since_days": args.get("days", 30)}
        if args.get("domains"):
            scan_params["domains"] = args["domains"]
        Path(self.runtime.state_path).write_text(json.dumps({"seen_ids": []}))
        result = self.runtime.execute_skill("scan_cycle", scan_params)
        if not result.success:
            raise RuntimeError(result.error)
        results = json.loads(
            json.dumps(result.data["results"], default=enum_serializer)
        )
        return {
            "status": "success",
            "filings_analyzed": len(results),
            "results": results,
        }

    def _recall(self, args: dict) -> list:
        result = self.runtime.execute_skill("recall_memory", args)
        if not result.success:
            raise RuntimeError(result.error)
        return result.data

    def _feedback(self, args: dict) -> dict:
        result = self.runtime.execute_skill("record_feedback", args)
        if not result.success:
            raise RuntimeError(result.error)
        return {"status": "recorded", "result": result.data}

    def _relations(self, args: dict) -> list:
        return self.memory.get_related_entities(args["entity"])

    def _stats(self, args: dict) -> dict:
        return self.memory.stats()

    # ── OpenViking handlers ──────────────────────────────────────────────

    def _ov_search(self, args: dict) -> Any:
        return ov_bridge.ov_search(
            query=args["query"],
            target_uri=args.get("target_uri", ""),
            limit=args.get("limit", 10),
        )

    def _ov_read(self, args: dict) -> str:
        return ov_bridge.ov_read(args["uri"])

    def _ov_list(self, args: dict) -> list:
        return ov_bridge.ov_list(args.get("uri", "viking://"))

    def _ov_add_resource(self, args: dict) -> dict:
        return ov_bridge.ov_add_resource(path=args["path"], wait=args.get("wait", True))

    def _ov_grep(self, args: dict) -> dict:
        return ov_bridge.ov_grep(
            uri=args["uri"],
            pattern=args["pattern"],
            case_insensitive=args.get("case_insensitive", False),
        )

    def _ov_glob(self, args: dict) -> dict:
        return ov_bridge.ov_glob(
            pattern=args["pattern"], uri=args.get("uri", "viking://")
        )

    def _ov_memory_commit(self, args: dict) -> dict:
        return ov_bridge.ov_commit_session(args["session_id"])

    def _scan_state_filings(self, args: dict) -> dict:
        from app.naturalsentinel.fetchers.base import fetch_filings
        from app.naturalsentinel.models import IndustrySector, Jurisdiction, StateCode

        raw_states = args.get("state_codes") or []
        if raw_states == ["all"]:
            raw_states = []
        state_codes = [
            StateCode(sc) for sc in raw_states if sc in [e.value for e in StateCode]
        ]
        raw_sectors = args.get("sectors") or []
        sectors = [
            IndustrySector(s)
            for s in raw_sectors
            if s in [e.value for e in IndustrySector]
        ]
        since_days = int(args.get("since_days", 7))
        include_federal = bool(args.get("include_federal", False))
        jurisdiction = None if include_federal else Jurisdiction.STATE

        filings = fetch_filings(
            sectors=sectors or None,
            state_codes=state_codes or None,
            jurisdiction=jurisdiction,
            since_days=since_days,
            live=True,
            fetch_full_text=False,
        )
        grouped: dict[str, dict[str, list]] = {}
        for f in filings:
            key = f.state_code.value if f.state_code else f.jurisdiction.value
            for sector in f.industry_sectors or [f.domain.value]:
                grouped.setdefault(key, {}).setdefault(sector, []).append(
                    {
                        "id": f.id,
                        "title": f.title,
                        "published_date": f.published_date,
                        "change_type": f.change_type.value,
                    }
                )
        return {"total": len(filings), "grouped": grouped}

    def _get_sector_regulatory_calendar(self, args: dict) -> dict:

        from app.naturalsentinel.fetchers.base import fetch_filings
        from app.naturalsentinel.models import IndustrySector, Jurisdiction, StateCode

        sector = args.get("sector", "")
        try:
            sector_enum = IndustrySector(sector)
        except ValueError:
            return {"error": f"Unknown sector: {sector}"}
        state_filter = args.get("state_codes") or []
        state_codes = [
            StateCode(sc) for sc in state_filter if sc in [e.value for e in StateCode]
        ]
        months_ahead = int(args.get("months_ahead", 3))
        filings = fetch_filings(
            sectors=[sector_enum],
            state_codes=state_codes or None,
            jurisdiction=Jurisdiction.STATE,
            since_days=months_ahead * 31,
            live=True,
            fetch_full_text=False,
        )
        today_str = datetime.now(UTC).strftime("%Y-%m-%d")
        entries = sorted(
            [
                {
                    "date": f.published_date,
                    "title": f.title,
                    "state": f.state_code.value if f.state_code else "federal",
                    "change_type": f.change_type.value,
                    "source_url": f.source_url,
                }
                for f in filings
                if f.published_date >= today_str
            ],
            key=lambda x: x["date"],
        )
        return {"sector": sector, "total": len(entries), "calendar": entries}

    def _read_resource(self, uri: str) -> Any:
        if uri == "naturalsentinel://memory/stats":
            return self.memory.stats()
        elif uri == "naturalsentinel://config/domains":
            return {
                "domains": [d.value for d in RegulatoryDomain],
                "business_lines": DOMAIN_BUSINESS_LINES,
            }
        return {"error": f"Unknown resource: {uri}"}

    def run_stdio(self):
        """Read JSON lines from stdin, write responses to stdout."""
        print(  # noqa: T201
            json.dumps({"status": "ready", "server": "regulatory-monitor-standalone"}),
            flush=True,
        )
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.handle_request(request)
                print(json.dumps(response), flush=True)  # noqa: T201
            except Exception as e:
                print(json.dumps({"error": str(e)}), flush=True)  # noqa: T201


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════


async def run_mcp_server(transport: str = "stdio"):
    """Run the full MCP server."""
    server = create_mcp_server()

    if transport == "stdio":
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream)
    elif transport == "sse":
        import uvicorn
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route

        sse = SseServerTransport("/messages")
        app = Starlette(
            routes=[
                Route("/sse", endpoint=sse.handle_sse_connection),
                Route("/messages", endpoint=sse.handle_post_message, methods=["POST"]),
            ]
        )
        uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
    elif transport == "streamable":
        import uvicorn
        from mcp.server.streamable_http import StreamableHTTPServerTransport

        # Streamable HTTP is the newest MCP transport
        transport_obj = StreamableHTTPServerTransport(
            host="0.0.0.0", port=int(os.getenv("PORT", "8080"))
        )
        await server.run_with_transport(transport_obj)
    else:
        raise ValueError(f"Unknown transport: {transport}")


def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(description="Regulatory Monitor MCP Server")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse", "streamable", "standalone"],
        help="Transport mode: stdio (Claude Desktop), sse (web), streamable (HTTP), standalone (no MCP SDK)",
    )
    args = parser.parse_args()

    if args.transport == "standalone" or not HAS_MCP:
        if not HAS_MCP:
            logger.warning("MCP SDK not installed — running in standalone mode")
        server = StandaloneServer()
        server.run_stdio()
    else:
        import asyncio

        asyncio.run(run_mcp_server(args.transport))


def create_mcp_app() -> StandaloneServer:
    """Return a StandaloneServer instance for in-process use from FastAPI.

    Called during app lifespan startup so the MCP server shares the same
    process (and eventually the same DB session) as the FastAPI application.
    """
    return StandaloneServer()


if __name__ == "__main__":
    main()
