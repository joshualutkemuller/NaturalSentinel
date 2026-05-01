"""MCP tool registry — single source of truth for tool dispatch.

**Phase R.5 step 6 scaffold.** The registry is empty in this commit;
Phase P2.1 will populate it by moving the 15+ tools currently hand-
wired in ``mcp/server.py`` into per-tool files under ``mcp/handlers/``.

Problem this solves
-------------------
Today there are **two parallel tool dispatch chains** in server.py:

1. The MCP SDK path — ``create_mcp_server()`` with
   ``@server.list_tools()`` defining tools and ``_handle_tool()`` with
   a ~250-line ``if/elif`` chain dispatching by name.

2. The ``StandaloneServer`` path — a ``self.tools`` dict mapping names
   to methods, with each tool reimplemented as a ``_method(args)``
   handler on the class.

Adding a new tool requires editing **three places**:

- ``list_tools()`` to declare the schema
- ``_handle_tool()`` to add the elif branch
- ``StandaloneServer.tools`` + corresponding ``_method`` implementation

And at least one tool (``analyze_filing_text``) is already broken —
it exists in the MCP SDK path but is missing from ``StandaloneServer``,
so clients using the standalone transport get
``"Unknown tool: analyze_filing_text"``. The drift was only caught by
a parity test in Phase P0.1.

Target shape (populated in Phase P2.1)
---------------------------------------
A single ``TOOL_REGISTRY`` dict that both dispatch paths read from::

    @dataclass(frozen=True)
    class ToolSpec:
        name: str
        description: str
        input_schema: dict
        handler: Callable[[dict], dict | str]

    TOOL_REGISTRY: dict[str, ToolSpec] = {}

    def register_tool(spec: ToolSpec) -> None: ...
    def get_tool(name: str) -> ToolSpec: ...
    def list_tools() -> list[ToolSpec]: ...

Each handler lives in ``mcp/handlers/<tool_name>.py`` and calls
``register_tool(ToolSpec(...))`` at module import time. Both
``create_mcp_server()`` and ``StandaloneServer`` consume the registry
— adding a new tool becomes a one-place edit.

Until P2.1 lands, this file is a placeholder so plan cross-refs work.
"""

from __future__ import annotations

# Populated by Phase P2.1 (not in this commit).
TOOL_REGISTRY: dict[str, object] = {}
