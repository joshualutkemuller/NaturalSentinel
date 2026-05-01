"""Tests for naturalsentinel.mcp — standalone MCP server tool dispatch."""

import pytest


class TestStandaloneServer:
    """Test the StandaloneServer which works without the MCP SDK."""

    @pytest.fixture
    def server(self, memory):
        import app.naturalsentinel.mcp.server as mcp_mod

        mcp_mod._memory = memory
        from app.naturalsentinel.mcp.server import StandaloneServer

        return StandaloneServer()

    @pytest.fixture
    def populated_memory(self, memory):
        memory.store_episodic(
            "SEC-001",
            {
                "id": "SEC-001",
                "title": "Climate Rule",
                "domain": "sec",
                "summary": "SEC climate.",
            },
            {
                "severity": "critical",
                "affected_business_lines": ["ESG"],
                "affected_regulations": ["Reg S-K"],
                "risk_summary": "Risk",
            },
        )
        memory.record_feedback(
            "SEC-001", "severity", "critical", "critical", "confirmed"
        )
        return memory

    # -- tools/list ---------------------------------------------------------

    def test_tools_list(self, server):
        resp = server.handle_request({"method": "tools/list", "params": {}})
        assert "tools" in resp
        assert isinstance(resp["tools"], list)
        assert len(resp["tools"]) >= 4

    # -- tools/call: get_memory_stats ---------------------------------------

    def test_memory_stats(self, server):
        resp = server.handle_request(
            {
                "method": "tools/call",
                "params": {"name": "get_memory_stats", "arguments": {}},
            }
        )
        result = resp["result"]
        assert "total_memories" in result
        assert "by_type" in result

    # -- tools/call: recall_memory ------------------------------------------

    def test_recall_memory(self, server, populated_memory):
        resp = server.handle_request(
            {
                "method": "tools/call",
                "params": {
                    "name": "recall_memory",
                    "arguments": {"query": "climate SEC", "top_k": 2},
                },
            }
        )
        assert isinstance(resp["result"], list)
        assert len(resp["result"]) > 0
        assert resp["result"][0]["key"] == "SEC-001"

    def test_recall_memory_with_type_filter(self, server, populated_memory):
        resp = server.handle_request(
            {
                "method": "tools/call",
                "params": {
                    "name": "recall_memory",
                    "arguments": {
                        "query": "severity correction",
                        "memory_type": "precedent",
                        "top_k": 5,
                    },
                },
            }
        )
        results = resp["result"]
        # All returned should be precedent type (if any returned)
        for r in results:
            assert "precedent" in r["id"]

    def test_missing_query_argument_returns_error(self, server):
        resp = server.handle_request(
            {
                "method": "tools/call",
                "params": {"name": "recall_memory", "arguments": {}},
            }
        )
        assert "error" in resp
        assert "query" in resp["error"]

    def test_invalid_memory_type_returns_error(self, server):
        resp = server.handle_request(
            {
                "method": "tools/call",
                "params": {
                    "name": "recall_memory",
                    "arguments": {"query": "climate", "memory_type": "bogus"},
                },
            }
        )
        assert "error" in resp
        assert "bogus" in resp["error"]

    def test_missing_feedback_field_returns_error(self, server):
        resp = server.handle_request(
            {
                "method": "tools/call",
                "params": {
                    "name": "provide_feedback",
                    "arguments": {"filing_id": "SEC-001", "field": "severity"},
                },
            }
        )
        assert "error" in resp

    def test_stats_response_contract(self, server):
        resp = server.handle_request(
            {
                "method": "tools/call",
                "params": {"name": "get_memory_stats", "arguments": {}},
            }
        )
        result = resp["result"]
        assert {"total_memories", "by_type", "total_relations"} <= set(result.keys())

    # -- tools/call: provide_feedback ---------------------------------------

    def test_provide_feedback(self, server, populated_memory):
        resp = server.handle_request(
            {
                "method": "tools/call",
                "params": {
                    "name": "provide_feedback",
                    "arguments": {
                        "filing_id": "SEC-001",
                        "field": "affected_business_lines",
                        "old_value": "ESG",
                        "new_value": "ESG, Investment Banking",
                        "reason": "missed IB impact",
                    },
                },
            }
        )
        assert resp["result"]["status"] == "recorded"

    # -- tools/call: get_entity_relations -----------------------------------

    def test_entity_relations(self, server, populated_memory):
        resp = server.handle_request(
            {
                "method": "tools/call",
                "params": {
                    "name": "get_entity_relations",
                    "arguments": {"entity": "Reg S-K"},
                },
            }
        )
        assert isinstance(resp["result"], list)

    # -- tools/call: unknown tool -------------------------------------------

    def test_unknown_tool(self, server):
        resp = server.handle_request(
            {
                "method": "tools/call",
                "params": {"name": "nonexistent_tool", "arguments": {}},
            }
        )
        assert "error" in resp

    # -- resources/list -----------------------------------------------------

    def test_resources_list(self, server):
        resp = server.handle_request({"method": "resources/list", "params": {}})
        assert "resources" in resp
        assert "naturalsentinel://memory/stats" in resp["resources"]

    # -- resources/read -----------------------------------------------------

    def test_read_memory_stats(self, server):
        resp = server.handle_request(
            {
                "method": "resources/read",
                "params": {"uri": "naturalsentinel://memory/stats"},
            }
        )
        assert "total_memories" in resp["result"]

    def test_read_config_domains(self, server):
        resp = server.handle_request(
            {
                "method": "resources/read",
                "params": {"uri": "naturalsentinel://config/domains"},
            }
        )
        result = resp["result"]
        assert "domains" in result
        assert "sec" in result["domains"]
        assert "business_lines" in result

    def test_read_unknown_resource(self, server):
        resp = server.handle_request(
            {
                "method": "resources/read",
                "params": {"uri": "naturalsentinel://nonexistent"},
            }
        )
        assert "error" in resp["result"]

    # -- unknown method -----------------------------------------------------

    def test_unknown_method(self, server):
        resp = server.handle_request({"method": "bogus/method", "params": {}})
        assert "error" in resp


class TestMcpDispatchParity:
    """Guard rail: every tool surfaced on the MCP SDK path must also
    exist on the StandaloneServer transport (and vice versa).

    When a new tool is added we want one place to edit, not three; until
    the Phase P2.1 registry lands this test catches the drift that
    caused the original ``analyze_filing_text`` bug (defined in the MCP
    SDK ``_handle_tool`` but missing from ``StandaloneServer.tools``).
    """

    def _parse_handle_tool_branches(self) -> set[str]:
        """Scrape tool names from the ``_handle_tool`` if/elif chain.

        Walks the AST of ``create_mcp_server`` and locates the inner
        ``_handle_tool`` function, then collects every ``name == "..."``
        comparison inside it. Scoping to the function body avoids picking
        up prompt-handler branches that share the same variable name.
        """
        import ast
        import inspect
        import textwrap

        import app.naturalsentinel.mcp.server as mcp_mod

        source = textwrap.dedent(inspect.getsource(mcp_mod.create_mcp_server))
        tree = ast.parse(source)

        handle_tool_node: ast.FunctionDef | None = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_handle_tool":
                handle_tool_node = node
                break
        assert handle_tool_node is not None, (
            "Could not find _handle_tool inside create_mcp_server"
        )

        names: set[str] = set()
        for node in ast.walk(handle_tool_node):
            if (
                isinstance(node, ast.Compare)
                and isinstance(node.left, ast.Name)
                and node.left.id == "name"
                and len(node.ops) == 1
                and isinstance(node.ops[0], ast.Eq)
                and len(node.comparators) == 1
                and isinstance(node.comparators[0], ast.Constant)
                and isinstance(node.comparators[0].value, str)
            ):
                names.add(node.comparators[0].value)
        return names

    def test_both_surfaces_expose_the_same_tools(self, memory):
        """StandaloneServer.tools and the MCP SDK branches must match."""
        import app.naturalsentinel.mcp.server as mcp_mod

        mcp_mod._memory = memory
        from app.naturalsentinel.mcp.server import StandaloneServer

        sdk_tools = self._parse_handle_tool_branches()
        standalone_tools = set(StandaloneServer().tools.keys())

        missing_from_standalone = sdk_tools - standalone_tools
        missing_from_sdk = standalone_tools - sdk_tools

        assert not missing_from_standalone, (
            f"Tools defined on MCP SDK path but missing from StandaloneServer: "
            f"{sorted(missing_from_standalone)}"
        )
        assert not missing_from_sdk, (
            f"Tools defined on StandaloneServer but missing from MCP SDK path: "
            f"{sorted(missing_from_sdk)}"
        )

    def test_analyze_filing_text_dispatches_on_standalone(self, memory, monkeypatch):
        """Regression test for the original bug — calling
        ``analyze_filing_text`` through the standalone transport must
        not return ``Unknown tool``.
        """
        import app.naturalsentinel.mcp.server as mcp_mod

        mcp_mod._memory = memory
        from app.naturalsentinel.mcp.server import StandaloneServer

        server = StandaloneServer()
        assert "analyze_filing_text" in server.tools
