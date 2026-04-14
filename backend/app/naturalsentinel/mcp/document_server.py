"""
document_server.py — MCP Server for Document Intelligence
==========================================================

Exposes the Document Intelligence pipeline as a second MCP server:

TOOLS
  ingest_document          — Parse, tier, and dual-write a document to OV + Qdrant
  recall_context           — Tiered RRF retrieval across indexed documents
  follow_process           — Step-by-step document review against a process definition
  list_documents           — List documents ingested into the pipeline
  document_status          — Get structure summary for a specific doc_id
  register_process         — Upload and register a process definition

RESOURCES
  doc://{doc_id}/structure — L0/L1 structure summary for an ingested document
  process://registry       — All registered process definitions

PROMPTS
  document_review          — Initiate a structured document review workflow
  process_summary          — Summarise the results of a completed review session

Run with:
    python -m app.naturalsentinel.mcp.document_server            # stdio (default)
    python -m app.naturalsentinel.mcp.document_server --transport sse

Configure in Claude Desktop's claude_desktop_config.json:
{
  "mcpServers": {
    "document-intelligence": {
      "command": "python",
      "args": ["-m", "app.naturalsentinel.mcp.document_server"],
      "env": {
        "OPENVIKING_URL": "http://localhost:1933",
        "QDRANT_URL": "http://localhost:6333"
      }
    }
  }
}
"""

from __future__ import annotations

import json
import logging
import os
import sys
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

logger = logging.getLogger("DocumentMCP")

# ---------------------------------------------------------------------------
# Lazy client factories
# ---------------------------------------------------------------------------


def _get_ov_client():
    """Return a SyncHTTPClient connected to OpenViking, or None."""
    try:
        from app.naturalsentinel.mcp.openviking import _get_ov_client as _ov

        return _ov()
    except Exception:
        return None


def _get_qdrant_client():
    """Return a qdrant_client.QdrantClient, or None."""
    try:
        from qdrant_client import QdrantClient

        url = os.getenv("QDRANT_URL", "http://localhost:6333")
        return QdrantClient(url=url)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# MCP SERVER DEFINITION
# ═══════════════════════════════════════════════════════════════════════════


def create_document_mcp_server() -> Server:
    """Build and configure the Document Intelligence MCP server."""

    if not HAS_MCP:
        raise ImportError(
            "MCP SDK not installed. Run: pip install mcp\n"
            "See: https://modelcontextprotocol.io/quickstart/server"
        )

    server = Server("document-intelligence")

    # ───────────────────────────────────────────────────────────────────
    # TOOLS
    # ───────────────────────────────────────────────────────────────────

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="ingest_document",
                description=(
                    "Ingest a document (PDF, DOCX, HTML, Markdown, plain text) through "
                    "the Document Intelligence pipeline. Parses structural hierarchy, "
                    "generates L0/L1/L2 tiers, indexes embeddings in Qdrant, and writes "
                    "the hierarchy to OpenViking. Accepts a URL, absolute file path, or "
                    "base64-encoded content. Returns doc_id, viking:// URI, section count, "
                    "and L0 structure summary."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_url": {
                            "type": "string",
                            "description": "URL to fetch the document from.",
                            "default": "",
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Absolute local file path.",
                            "default": "",
                        },
                        "content_b64": {
                            "type": "string",
                            "description": "Base64-encoded file content.",
                            "default": "",
                        },
                        "content_type": {
                            "type": "string",
                            "description": "MIME type hint (e.g. application/pdf).",
                            "default": "",
                        },
                        "doc_type": {
                            "type": "string",
                            "enum": [
                                "legal",
                                "medical",
                                "compliance",
                                "generic",
                                "auto",
                            ],
                            "description": "Document type. 'auto' infers from content.",
                            "default": "auto",
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Extra metadata: tags, client_name, matter_id, etc.",
                            "default": {},
                        },
                    },
                },
            ),
            Tool(
                name="recall_context",
                description=(
                    "Retrieve relevant document context for a query using dual-path "
                    "retrieval (Qdrant kNN + OpenViking hierarchical search) fused via "
                    "Reciprocal Rank Fusion. Returns tiered context blocks (L0 abstract / "
                    "L1 overview / L2 detail) assembled within a configurable token budget, "
                    "plus retrieval trajectory metadata for source citation."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural-language question or information need.",
                        },
                        "doc_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Scope retrieval to these doc_ids. Empty = all indexed documents.",
                            "default": [],
                        },
                        "collections": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Qdrant collections to search. Default: ['ns_documents'].",
                            "default": [],
                        },
                        "token_budget": {
                            "type": "integer",
                            "description": "Max tokens in returned context (default: 6144).",
                            "default": 6144,
                        },
                        "depth": {
                            "type": "string",
                            "enum": ["abstract", "overview", "detail"],
                            "description": "Maximum retrieval tier: abstract=L0, overview=L1, detail=L2.",
                            "default": "overview",
                        },
                        "include_cross_references": {
                            "type": "boolean",
                            "description": "Follow cross-referenced sections (default: true).",
                            "default": True,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="follow_process",
                description=(
                    "Execute a registered document review process step by step. Each call "
                    "advances the review by one step, retrieves relevant document context "
                    "for that step, and returns instructions + context + progress tracking. "
                    "Sessions persist so reviews can be paused and resumed across calls."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "process_name": {
                            "type": "string",
                            "description": "Registered process definition name (e.g. 'contract_review').",
                        },
                        "doc_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Documents to review.",
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Resume an existing session. Omit to start a new one.",
                            "default": "",
                        },
                        "action": {
                            "type": "string",
                            "enum": ["start", "next", "skip", "status", "complete"],
                            "description": "Action: start (new), next (advance with findings), skip, status, complete.",
                            "default": "start",
                        },
                        "step_result": {
                            "type": "object",
                            "description": "Findings for the just-completed step: {findings: str, status: pass|fail|flagged|skipped}.",
                            "default": {},
                        },
                    },
                    "required": ["process_name", "doc_ids"],
                },
            ),
            Tool(
                name="list_documents",
                description=(
                    "List documents that have been ingested into the Document Intelligence "
                    "pipeline. Returns doc_id, title, doc_type, section count, and ingest "
                    "timestamp for each document. Optionally filter by doc_type."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "doc_type": {
                            "type": "string",
                            "enum": ["legal", "medical", "compliance", "generic"],
                            "description": "Filter by document type. Omit for all types.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max documents to return (default: 20).",
                            "default": 20,
                        },
                    },
                },
            ),
            Tool(
                name="document_status",
                description=(
                    "Get the structure summary and metadata for a specific ingested document. "
                    "Returns L0 abstract, section hierarchy, viking:// URI, and index status "
                    "in Qdrant (number of embedding points)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "doc_id": {
                            "type": "string",
                            "description": "The doc_id returned by ingest_document.",
                        },
                    },
                    "required": ["doc_id"],
                },
            ),
            Tool(
                name="register_process",
                description=(
                    "Upload and register a document review process definition. Process "
                    "definitions are markdown files with YAML front matter (name, version, "
                    "doc_types) and numbered ## Step N sections (instruction, retrieval_query, "
                    "target_sections). Once registered, the process can be executed via "
                    "follow_process."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Unique process name (e.g. 'contract_review', 'medical_intake').",
                        },
                        "definition_md": {
                            "type": "string",
                            "description": "Full markdown text of the process definition.",
                        },
                        "doc_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Document types this process applies to (e.g. ['legal', 'compliance']).",
                            "default": [],
                        },
                        "description": {
                            "type": "string",
                            "description": "Human-readable description of the process.",
                            "default": "",
                        },
                    },
                    "required": ["name", "definition_md"],
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
        ov = _get_ov_client()
        qdrant = _get_qdrant_client()

        if name == "ingest_document":
            from app.naturalsentinel.documents.pipeline import ingest_document

            source_url = args.get("source_url", "")
            file_path = args.get("file_path", "")
            content_b64 = args.get("content_b64", "")

            if not any([source_url, file_path, content_b64]):
                return json.dumps(
                    {"error": "Provide one of: source_url, file_path, content_b64"}
                )

            result = ingest_document(
                source_url=source_url,
                file_path=file_path,
                content_b64=content_b64,
                content_type=args.get("content_type", ""),
                doc_type=args.get("doc_type", "auto"),
                metadata=args.get("metadata", {}),
                ov_client=ov,
                qdrant_client=qdrant,
            )
            return json.dumps(result, indent=2, default=str)

        elif name == "recall_context":
            from app.naturalsentinel.documents.retrieval import recall_context

            query = args.get("query", "")
            if not query:
                return json.dumps({"error": "'query' is required"})

            result = recall_context(
                query=query,
                ov_client=ov,
                qdrant_client=qdrant,
                doc_ids=args.get("doc_ids") or None,
                collections=args.get("collections") or None,
                token_budget=int(args.get("token_budget", 6144)),
                depth=args.get("depth", "overview"),
                include_cross_references=bool(
                    args.get("include_cross_references", True)
                ),
            )
            return json.dumps(result, indent=2, default=str)

        elif name == "follow_process":
            from app.naturalsentinel.documents.process_engine import follow_process

            process_name = args.get("process_name", "")
            doc_ids = args.get("doc_ids", [])
            if not process_name or not doc_ids:
                return json.dumps(
                    {"error": "'process_name' and 'doc_ids' are required"}
                )

            result = follow_process(
                process_name=process_name,
                doc_ids=doc_ids,
                session_id=args.get("session_id") or None,
                action=args.get("action", "start"),
                step_result=args.get("step_result") or None,
                ov_client=ov,
                qdrant_client=qdrant,
                session_db=None,
            )
            return json.dumps(result, indent=2, default=str)

        elif name == "list_documents":
            return _list_documents(
                ov_client=ov,
                qdrant_client=qdrant,
                doc_type=args.get("doc_type"),
                limit=int(args.get("limit", 20)),
            )

        elif name == "document_status":
            doc_id = args.get("doc_id", "")
            if not doc_id:
                return json.dumps({"error": "'doc_id' is required"})
            return _document_status(doc_id=doc_id, ov_client=ov, qdrant_client=qdrant)

        elif name == "register_process":
            from app.naturalsentinel.documents.process_engine import register_process

            result = register_process(
                name=args.get("name", ""),
                definition_md=args.get("definition_md", ""),
                doc_types=args.get("doc_types", []),
                description=args.get("description", ""),
                ov_client=ov,
                session_db=None,
            )
            return json.dumps(result, indent=2, default=str)

        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    # ───────────────────────────────────────────────────────────────────
    # RESOURCES
    # ───────────────────────────────────────────────────────────────────

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="process://registry",
                name="Process Registry",
                description="All registered document review process definitions",
                mimeType="application/json",
            ),
        ]

    @server.list_resource_templates()
    async def list_resource_templates() -> list[ResourceTemplate]:
        return [
            ResourceTemplate(
                uriTemplate="doc://{doc_id}/structure",
                name="Document Structure",
                description="L0 abstract and section hierarchy for an ingested document",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        ov = _get_ov_client()
        qdrant = _get_qdrant_client()

        if uri == "process://registry":
            return _read_process_registry(ov_client=ov)

        if uri.startswith("doc://") and uri.endswith("/structure"):
            doc_id = uri[len("doc://") : -len("/structure")]
            return _document_status(doc_id=doc_id, ov_client=ov, qdrant_client=qdrant)

        return json.dumps({"error": f"Unknown resource: {uri}"})

    # ───────────────────────────────────────────────────────────────────
    # PROMPTS
    # ───────────────────────────────────────────────────────────────────

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name="document_review",
                description=(
                    "Initiate a structured document review workflow. Ingests the target "
                    "document (if not already indexed) and begins executing a named review "
                    "process step by step."
                ),
                arguments=[
                    PromptArgument(
                        name="doc_source",
                        description="URL or file path of the document to review",
                        required=True,
                    ),
                    PromptArgument(
                        name="process_name",
                        description="Registered review process to follow (e.g. 'contract_review')",
                        required=True,
                    ),
                    PromptArgument(
                        name="doc_type",
                        description="Document type: legal, medical, compliance, generic (default: auto)",
                        required=False,
                    ),
                ],
            ),
            Prompt(
                name="process_summary",
                description=(
                    "Summarise the results of a completed (or in-progress) review session. "
                    "Collects all step findings and produces a structured report with "
                    "flagged items, pass/fail counts, and recommended actions."
                ),
                arguments=[
                    PromptArgument(
                        name="session_id",
                        description="The review session ID to summarise",
                        required=True,
                    ),
                    PromptArgument(
                        name="process_name",
                        description="Process name used in the session",
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

        if name == "document_review":
            doc_source = args.get("doc_source", "")
            process_name = args.get("process_name", "contract_review")
            doc_type = args.get("doc_type", "auto")

            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Review the document at: {doc_source}\n\n"
                            f"Process: {process_name}\n"
                            f"Document type: {doc_type}\n\n"
                            "Steps:\n"
                            "1. Call ingest_document with the source to index it (if not already indexed). "
                            "   Note the returned doc_id.\n"
                            "2. Call follow_process with process_name='{process_name}', "
                            "   doc_ids=[doc_id], action='start' to begin.\n"
                            "3. For each step: read the returned instructions and context, "
                            "   evaluate the document against the step criteria, then call "
                            "   follow_process again with action='next' and your step_result "
                            "   (findings + status: pass|fail|flagged).\n"
                            "4. When all steps are complete, call follow_process with action='complete'.\n"
                            "5. Produce a final summary using the process_summary prompt."
                        ).format(process_name=process_name),
                    ),
                )
            ]

        elif name == "process_summary":
            session_id = args.get("session_id", "")
            process_name = args.get("process_name", "")

            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Summarise review session {session_id} (process: {process_name}).\n\n"
                            "Steps:\n"
                            "1. Call follow_process with session_id='{session_id}', "
                            "   process_name='{process_name}', doc_ids=[], action='status' "
                            "   to retrieve the full step record.\n"
                            "2. Produce a structured report containing:\n"
                            "   - Overall verdict (pass / fail / flagged)\n"
                            "   - Step-by-step summary table (step name, status, key findings)\n"
                            "   - All flagged items with source citations (section, page)\n"
                            "   - Recommended next actions\n"
                            "   - Review metadata (session_id, process_name, doc_ids, timestamp)"
                        ).format(session_id=session_id, process_name=process_name),
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
# Helper implementations
# ═══════════════════════════════════════════════════════════════════════════


def _list_documents(
    *,
    ov_client,
    qdrant_client,
    doc_type: str | None,
    limit: int,
) -> str:
    """List ingested documents from OpenViking."""
    docs: list[dict] = []

    if ov_client is not None:
        try:
            items = ov_client.ls("viking://documents/")
            for item in items[:limit]:
                entry: dict[str, Any] = {"uri": item}
                # Try to read L0 abstract for a one-line summary
                try:
                    abstract_uri = item.rstrip("/") + "/abstract.txt"
                    abstract = ov_client.read(abstract_uri)
                    entry["abstract"] = abstract[:200] if abstract else ""
                except Exception:
                    entry["abstract"] = ""
                docs.append(entry)
        except Exception as e:
            logger.warning("ov ls failed: %s", e)

    if not docs and qdrant_client is not None:
        # Fall back to Qdrant scroll
        try:
            scroll_result = qdrant_client.scroll(
                collection_name="ns_documents",
                with_payload=True,
                limit=limit,
            )
            seen: set[str] = set()
            for point in scroll_result[0]:
                payload = point.payload or {}
                doc_id = payload.get("doc_id", "")
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                if doc_type and payload.get("doc_type") != doc_type:
                    continue
                docs.append(
                    {
                        "doc_id": doc_id,
                        "doc_type": payload.get("doc_type", ""),
                        "source_url": payload.get("source_url", ""),
                    }
                )
        except Exception as e:
            logger.warning("qdrant scroll failed: %s", e)

    return json.dumps({"total": len(docs), "documents": docs}, indent=2, default=str)


def _document_status(*, doc_id: str, ov_client, qdrant_client) -> str:
    """Return structure summary for a single doc_id."""
    status: dict[str, Any] = {"doc_id": doc_id}

    base_uri = f"viking://documents/{doc_id}/"

    if ov_client is not None:
        try:
            # Read L0 abstract
            try:
                abstract = ov_client.read(base_uri + "abstract.txt")
                status["abstract"] = abstract
            except Exception:
                status["abstract"] = ""

            # List sections
            try:
                sections = ov_client.ls(base_uri)
                status["sections"] = sections
                status["section_count"] = len(sections)
            except Exception:
                status["sections"] = []
                status["section_count"] = 0

            status["uri"] = base_uri
        except Exception as e:
            status["ov_error"] = str(e)

    if qdrant_client is not None:
        try:
            result = qdrant_client.scroll(
                collection_name="ns_documents",
                scroll_filter={
                    "must": [
                        {"key": "doc_id", "match": {"value": doc_id}},
                        {"key": "level", "match": {"value": "L0"}},
                    ]
                },
                with_payload=True,
                limit=1,
            )
            if result[0]:
                payload = result[0][0].payload or {}
                status["doc_type"] = payload.get("doc_type", "")
                status["source_url"] = payload.get("source_url", "")

            # Count total embedding points
            count_result = qdrant_client.scroll(
                collection_name="ns_documents",
                scroll_filter={"must": [{"key": "doc_id", "match": {"value": doc_id}}]},
                with_payload=False,
                limit=1000,
            )
            status["qdrant_points"] = len(count_result[0])
        except Exception as e:
            logger.warning("qdrant status query failed: %s", e)

    return json.dumps(status, indent=2, default=str)


def _read_process_registry(*, ov_client) -> str:
    """Read registered process definitions from OpenViking."""
    registry: list[dict] = []

    if ov_client is not None:
        try:
            items = ov_client.ls("viking://processes/")
            for item in items:
                entry: dict[str, Any] = {"uri": item}
                try:
                    meta_uri = item.rstrip("/") + "/meta.json"
                    meta_raw = ov_client.read(meta_uri)
                    entry.update(json.loads(meta_raw))
                except Exception:
                    pass
                registry.append(entry)
        except Exception as e:
            logger.warning("ov process registry read failed: %s", e)

    return json.dumps(
        {"total": len(registry), "processes": registry}, indent=2, default=str
    )


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════


async def _run_stdio() -> None:
    server = create_document_mcp_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


def main() -> None:
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Document Intelligence MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    args = parser.parse_args()

    if not HAS_MCP:
        print(
            "ERROR: MCP SDK not installed. Run: pip install mcp",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.transport == "stdio":
        asyncio.run(_run_stdio())


if __name__ == "__main__":
    main()
