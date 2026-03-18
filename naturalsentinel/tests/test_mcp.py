"""Tests for naturalsentinel.mcp — standalone MCP server tool dispatch."""

import json
import pytest

from naturalsentinel.memory.store import MemoryStore
from naturalsentinel.memory.types import MemoryType
from naturalsentinel.models import RegulatoryDomain
from naturalsentinel.fetchers import DOMAIN_BUSINESS_LINES


class TestStandaloneServer:
    """Test the StandaloneServer which works without the MCP SDK."""

    @pytest.fixture
    def server(self, memory):
        import naturalsentinel.mcp.server as mcp_mod
        mcp_mod._memory = memory
        from naturalsentinel.mcp.server import StandaloneServer
        return StandaloneServer()

    @pytest.fixture
    def populated_memory(self, memory):
        memory.store_episodic(
            "SEC-001",
            {"id": "SEC-001", "title": "Climate Rule", "domain": "sec", "summary": "SEC climate."},
            {"severity": "critical", "affected_business_lines": ["ESG"], "affected_regulations": ["Reg S-K"], "risk_summary": "Risk"},
        )
        memory.record_feedback("SEC-001", "severity", "critical", "critical", "confirmed")
        return memory

    # -- tools/list ---------------------------------------------------------

    def test_tools_list(self, server):
        resp = server.handle_request({"method": "tools/list", "params": {}})
        assert "tools" in resp
        assert isinstance(resp["tools"], list)
        assert len(resp["tools"]) >= 4

    # -- tools/call: get_memory_stats ---------------------------------------

    def test_memory_stats(self, server):
        resp = server.handle_request({
            "method": "tools/call",
            "params": {"name": "get_memory_stats", "arguments": {}},
        })
        result = resp["result"]
        assert "total_memories" in result
        assert "by_type" in result

    # -- tools/call: recall_memory ------------------------------------------

    def test_recall_memory(self, server, populated_memory):
        resp = server.handle_request({
            "method": "tools/call",
            "params": {"name": "recall_memory", "arguments": {"query": "climate SEC", "top_k": 2}},
        })
        assert isinstance(resp["result"], list)
        assert len(resp["result"]) > 0
        assert resp["result"][0]["key"] == "SEC-001"

    def test_recall_memory_with_type_filter(self, server, populated_memory):
        resp = server.handle_request({
            "method": "tools/call",
            "params": {
                "name": "recall_memory",
                "arguments": {"query": "severity correction", "memory_type": "precedent", "top_k": 5},
            },
        })
        results = resp["result"]
        # All returned should be precedent type (if any returned)
        for r in results:
            assert "precedent" in r["id"]

    # -- tools/call: provide_feedback ---------------------------------------

    def test_provide_feedback(self, server, populated_memory):
        resp = server.handle_request({
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
        })
        assert resp["result"]["status"] == "recorded"

    # -- tools/call: get_entity_relations -----------------------------------

    def test_entity_relations(self, server, populated_memory):
        resp = server.handle_request({
            "method": "tools/call",
            "params": {"name": "get_entity_relations", "arguments": {"entity": "Reg S-K"}},
        })
        assert isinstance(resp["result"], list)

    # -- tools/call: unknown tool -------------------------------------------

    def test_unknown_tool(self, server):
        resp = server.handle_request({
            "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}},
        })
        assert "error" in resp

    # -- resources/list -----------------------------------------------------

    def test_resources_list(self, server):
        resp = server.handle_request({"method": "resources/list", "params": {}})
        assert "resources" in resp
        assert "naturalsentinel://memory/stats" in resp["resources"]

    # -- resources/read -----------------------------------------------------

    def test_read_memory_stats(self, server):
        resp = server.handle_request({
            "method": "resources/read",
            "params": {"uri": "naturalsentinel://memory/stats"},
        })
        assert "total_memories" in resp["result"]

    def test_read_config_domains(self, server):
        resp = server.handle_request({
            "method": "resources/read",
            "params": {"uri": "naturalsentinel://config/domains"},
        })
        result = resp["result"]
        assert "domains" in result
        assert "sec" in result["domains"]
        assert "business_lines" in result

    def test_read_unknown_resource(self, server):
        resp = server.handle_request({
            "method": "resources/read",
            "params": {"uri": "naturalsentinel://nonexistent"},
        })
        assert "error" in resp["result"]

    # -- unknown method -----------------------------------------------------

    def test_unknown_method(self, server):
        resp = server.handle_request({"method": "bogus/method", "params": {}})
        assert "error" in resp
