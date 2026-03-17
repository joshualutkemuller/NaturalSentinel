"""Tests for naturalsentinel.memory — persistent memory store."""

import json
import pytest
from naturalsentinel.memory.store import MemoryStore
from naturalsentinel.memory.types import MemoryType, MemoryRecord
from naturalsentinel.memory.similarity import SimilarityEngine


class TestMemoryStoreBasics:
    def test_empty_store(self, memory):
        assert memory.count() == 0
        assert memory.stats()["total_memories"] == 0

    def test_store_episodic(self, memory):
        memory.store_episodic(
            "TEST-001",
            {"title": "Test Filing", "domain": "sec", "summary": "A test."},
            {"severity": "high", "affected_business_lines": ["Equities"], "affected_regulations": ["Reg S-K"], "risk_summary": "Risk."},
        )
        assert memory.count() == 1
        assert memory.count(MemoryType.EPISODIC) == 1

    def test_store_entity(self, memory):
        memory.store_entity("Regulation S-K", {"type": "regulation", "agency": "SEC"})
        assert memory.count(MemoryType.ENTITY) == 1

    def test_record_feedback(self, memory):
        # Need an episodic first for context
        memory.store_episodic("TEST-001", {"title": "Test", "domain": "sec"}, {"severity": "medium"})
        memory.record_feedback("TEST-001", "severity", "medium", "high", "has enforcement risk")
        assert memory.count(MemoryType.PRECEDENT) == 1
        stats = memory.stats()
        assert stats["total_feedback"] == 1


class TestMemoryRetrieval:
    def test_get_by_id(self, memory):
        memory.store_episodic("TEST-001", {"title": "Climate Rule"}, {"severity": "high"})
        record = memory.get("episodic:TEST-001")
        assert record is not None
        assert record.key == "TEST-001"
        assert record.memory_type == MemoryType.EPISODIC

    def test_get_nonexistent(self, memory):
        assert memory.get("nonexistent:123") is None

    def test_recall_semantic(self, memory):
        memory.store_episodic("SEC-001", {"title": "Climate Disclosure", "domain": "sec"}, {"severity": "high", "affected_business_lines": ["ESG"], "affected_regulations": [], "risk_summary": "SEC enforcement"})
        memory.store_episodic("FDA-001", {"title": "Medical Device AI", "domain": "fda"}, {"severity": "medium", "affected_business_lines": ["Devices"], "affected_regulations": [], "risk_summary": "FDA guidance"})

        results = memory.recall("climate SEC ESG", top_k=2)
        assert len(results) > 0
        # The SEC filing should rank higher
        assert results[0].key == "SEC-001"

    def test_recall_with_type_filter(self, memory):
        memory.store_episodic("T-001", {"title": "Test", "domain": "sec"}, {"severity": "high"})
        memory.record_feedback("T-001", "severity", "high", "critical", "reason")

        eps = memory.recall("test", top_k=5, memory_type=MemoryType.EPISODIC)
        precs = memory.recall("test", top_k=5, memory_type=MemoryType.PRECEDENT)
        assert all(r.memory_type == MemoryType.EPISODIC for r in eps)
        assert all(r.memory_type == MemoryType.PRECEDENT for r in precs)

    def test_filing_history(self, memory):
        memory.store_episodic("SEC-001", {"title": "A", "domain": "sec"}, {"severity": "high"})
        memory.store_episodic("FDA-001", {"title": "B", "domain": "fda"}, {"severity": "low"})
        memory.store_episodic("SEC-002", {"title": "C", "domain": "sec"}, {"severity": "medium"})

        all_history = memory.get_filing_history()
        assert len(all_history) == 3

        sec_history = memory.get_filing_history(domain="sec")
        assert len(sec_history) == 2
        assert all(r.namespace == "sec" for r in sec_history)


class TestEntityRelations:
    def test_relations_auto_created(self, memory):
        memory.store_episodic(
            "T-001",
            {"title": "Test", "domain": "sec"},
            {
                "severity": "high",
                "affected_business_lines": ["Equities", "ESG"],
                "affected_regulations": ["Reg S-K"],
                "risk_summary": "Risk",
            },
        )
        rels = memory.get_related_entities("Reg S-K")
        assert len(rels) > 0

    def test_relation_weight_accumulates(self, memory):
        memory.store_episodic("T-001", {"title": "A", "domain": "sec"}, {"severity": "high", "affected_business_lines": ["Equities"], "affected_regulations": ["Reg S-K"], "risk_summary": "R"})
        memory.store_episodic("T-002", {"title": "B", "domain": "sec"}, {"severity": "high", "affected_business_lines": ["Equities"], "affected_regulations": ["Reg S-K"], "risk_summary": "R"})

        rels = memory.get_related_entities("Reg S-K")
        # Weight should be > 1.0 after two filings referencing the same pair
        equities_rels = [r for r in rels if r["target"] == "Equities" and r["relation"] == "impacts"]
        assert len(equities_rels) > 0
        assert equities_rels[0]["weight"] > 1.0


class TestContextBlock:
    def test_empty_memory_returns_empty(self, memory):
        assert memory.build_context_block("sec", "some text") == ""

    def test_context_includes_past_analyses(self, memory):
        memory.store_episodic("SEC-001", {"id": "SEC-001", "title": "Climate Rule", "domain": "sec"}, {"severity": "critical", "affected_business_lines": ["ESG"], "affected_regulations": [], "risk_summary": "R"})
        ctx = memory.build_context_block("sec", "climate disclosure")
        assert "RELEVANT PAST ANALYSES" in ctx
        assert "SEC-001" in ctx

    def test_context_includes_precedents(self, memory):
        memory.store_episodic("T-001", {"title": "Test", "domain": "sec"}, {"severity": "medium"})
        memory.record_feedback("T-001", "severity", "medium", "critical", "important")
        ctx = memory.build_context_block("sec", "regulatory correction important")
        assert "CORRECTION PRECEDENTS" in ctx


class TestExportImport:
    def test_roundtrip(self, memory):
        memory.store_episodic("T-001", {"title": "Test"}, {"severity": "high"})
        memory.record_feedback("T-001", "severity", "high", "critical", "reason")

        exported = memory.export_json()
        data = json.loads(exported)
        assert len(data["memories"]) == 2  # 1 episodic + 1 precedent

        # Import into a fresh store
        fresh = MemoryStore(":memory:")
        fresh.import_json(exported)
        assert fresh.count() == 2
        fresh.close()


class TestSimilarityEngine:
    def test_index_and_search(self):
        engine = SimilarityEngine()
        engine.index({
            "doc1": "climate disclosure SEC greenhouse gas emissions",
            "doc2": "medical device AI machine learning FDA",
            "doc3": "tariff semiconductor supply chain China",
        })
        results = engine.search("climate SEC ESG", top_k=2)
        assert len(results) > 0
        assert results[0][0] == "doc1"  # most relevant

    def test_empty_index(self):
        engine = SimilarityEngine()
        assert engine.search("anything") == []

    def test_backend_attribute(self):
        engine = SimilarityEngine()
        assert engine.backend in ("sklearn", "keyword")
