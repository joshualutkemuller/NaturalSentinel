"""Tests for naturalsentinel.agent — the core monitoring agent."""

import json

from app.naturalsentinel.models import RegulatoryDomain, Severity


class TestAgentRun:
    def test_run_returns_results(self, agent):
        results = agent.run(since_days=90)
        assert len(results) >= 6

    def test_results_have_correct_structure(self, agent):
        results = agent.run(since_days=90)
        for r in results:
            assert r.filing.id
            assert r.filing.title
            assert r.impact.filing_id == r.filing.id
            assert r.impact.severity in Severity
            assert 0.0 <= r.impact.confidence <= 1.0
            assert len(r.impact.action_items) > 0
            assert isinstance(r.evidence_ledger, list)

    def test_deduplication(self, agent):
        first = agent.run(since_days=90)
        second = agent.run(since_days=90)
        assert len(first) >= 6
        assert len(second) == 0  # all already seen

    def test_reset_state(self, agent):
        agent.run(since_days=90)
        agent.reset_state()
        after_reset = agent.run(since_days=90)
        assert len(after_reset) >= 6

    def test_domain_filtering(self, agent):
        agent.domains = [RegulatoryDomain.SEC, RegulatoryDomain.FDA]
        results = agent.run(since_days=90)
        domains = {r.filing.domain for r in results}
        assert domains <= {RegulatoryDomain.SEC, RegulatoryDomain.FDA}

    def test_run_json_valid(self, agent):
        output = agent.run_json(since_days=90)
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) >= 6
        # Check that enums are resolved to strings
        for item in data:
            assert isinstance(item["filing"]["domain"], str)
            assert isinstance(item["impact"]["severity"], str)


class TestAgentMemoryIntegration:
    def test_results_stored_in_memory(self, agent, memory):
        agent.run(since_days=90)
        assert memory.count() >= 6
        # All should be episodic
        from app.naturalsentinel.memory.types import MemoryType

        assert memory.count(MemoryType.EPISODIC) >= 6

    def test_entity_relations_created(self, agent, memory):
        agent.run(since_days=90)
        stats = memory.stats()
        assert stats["total_relations"] > 0

    def test_memory_context_injected(self, agent, memory):
        """After a first run, the second run should inject memory context."""
        agent.run(since_days=90)
        # Memory context should exist for a SEC query
        ctx = memory.build_context_block("sec", "climate disclosure requirements")
        assert "RELEVANT PAST ANALYSES" in ctx

    def test_agent_without_memory(self, mock_provider, tmp_path):
        """Agent should work fine without memory attached."""
        from app.naturalsentinel.agent import RegulatoryMonitorAgent

        agent = RegulatoryMonitorAgent(
            provider=mock_provider,
            memory=None,
            state_path=str(tmp_path / "state.json"),
        )
        results = agent.run(since_days=90)
        assert len(results) >= 6
