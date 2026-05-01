"""MCP tool handlers — one file per tool.

**Phase R.5 step 6 scaffold.** This directory is empty in this commit.
Phase P2.1 will populate it with one file per MCP tool, each of which
calls ``register_tool(ToolSpec(...))`` at import time to add itself to
``mcp.tool_registry.TOOL_REGISTRY``.

Planned handlers (from the current mcp/server.py dispatch chain)::

    scan_filings.py           — scan_regulatory_filings
    analyze_filing_text.py    — analyze_filing_text
    recall_memory.py          — recall_memory
    provide_feedback.py       — provide_feedback
    entity_relations.py       — get_entity_relations
    memory_stats.py           — get_memory_stats
    openviking.py             — the 7 OV bridge tools grouped
    scan_state_filings.py     — scan_state_filings
    sector_calendar.py        — get_sector_regulatory_calendar
    document_ingest.py        — document ingest via MCP
    document_recall.py        — document recall via MCP
    follow_process.py         — follow_process via MCP

Keeping one file per tool makes tool definitions self-contained and
independently reviewable, and makes adding a tool a one-place edit
(create the file; it registers itself on import).
"""
