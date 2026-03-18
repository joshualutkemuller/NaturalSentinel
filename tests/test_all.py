"""
Comprehensive test suite for naturalsentinel — runs with stdlib unittest.

    PYTHONPATH=src python -m unittest tests.test_all -v
"""

import json
import os
import tempfile
import unittest

# Ensure src is importable
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from naturalsentinel import (
    RegulatoryMonitorAgent,
    MockProvider,
    MemoryStore,
    EvidenceLedgerEntry,
    MemoryRecord,
    MemoryType,
    RegulatoryDomain,
    RegulatoryFiling,
    ImpactAssessment,
    DecisionFrame,
    MonitorResult,
    Severity,
    ChangeType,
)
from naturalsentinel.utils.parsing import extract_json_block, parse_llm_json
from naturalsentinel.utils.serialization import enum_serializer, serialize_result
from naturalsentinel.utils.text import tokenize, keyword_similarity
from naturalsentinel.fetchers import fetch_filings, DOMAIN_BUSINESS_LINES
from naturalsentinel.fetchers.sample_data import SAMPLE_FILINGS, MOCK_ANALYSES
from naturalsentinel.memory.similarity import SimilarityEngine
from naturalsentinel.cli import build_provider


# ══════════════════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════════════════

class TestEnums(unittest.TestCase):
    def test_domain_values(self):
        self.assertEqual(RegulatoryDomain.SEC.value, "sec")
        self.assertGreaterEqual(len(RegulatoryDomain), 6)

    def test_severity_values(self):
        vals = [s.value for s in Severity]
        self.assertEqual(vals, ["low", "medium", "high", "critical"])

    def test_change_type_roundtrip(self):
        for ct in ChangeType:
            self.assertIs(ChangeType(ct.value), ct)

    def test_domain_from_string(self):
        self.assertIs(RegulatoryDomain("cfpb"), RegulatoryDomain.CFPB)


class TestDataclasses(unittest.TestCase):
    def test_filing_defaults(self):
        f = RegulatoryFiling(
            id="T-001", title="Test", domain=RegulatoryDomain.SEC,
            source_url="https://x.com", published_date="2026-01-01", raw_text="text",
        )
        self.assertEqual(f.change_type, ChangeType.NOTICE)
        self.assertEqual(f.summary, "")
        self.assertTrue(f.fetched_at)

    def test_impact_assessment(self):
        ia = ImpactAssessment(
            filing_id="T-001", severity=Severity.HIGH,
            affected_business_lines=["Lending"], affected_regulations=["ECOA"],
            compliance_deadline="2026-12-31", action_items=["[Legal] Review"],
            risk_summary="High risk.", confidence=0.85,
        )
        self.assertEqual(ia.confidence, 0.85)


# ══════════════════════════════════════════════════════════════════════════
# UTILS — TEXT
# ══════════════════════════════════════════════════════════════════════════

class TestTokenize(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(tokenize("Hello, World!"), ["hello", "world"])

    def test_empty(self):
        self.assertEqual(tokenize(""), [])
        self.assertEqual(tokenize("!!!"), [])


class TestKeywordSimilarity(unittest.TestCase):
    def test_identical(self):
        t = ["climate", "sec"]
        self.assertEqual(keyword_similarity(t, t), 1.0)

    def test_no_overlap(self):
        self.assertEqual(keyword_similarity(["apple"], ["car"]), 0.0)

    def test_partial(self):
        s = keyword_similarity(["climate", "sec"], ["climate", "fda"])
        self.assertGreater(s, 0.0)
        self.assertLess(s, 1.0)

    def test_empty(self):
        self.assertEqual(keyword_similarity([], ["x"]), 0.0)


# ══════════════════════════════════════════════════════════════════════════
# UTILS — PARSING
# ══════════════════════════════════════════════════════════════════════════

class TestExtractJsonBlock(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(extract_json_block('{"k": "v"}'), '{"k": "v"}')

    def test_fenced(self):
        r = extract_json_block('```json\n{"k": "v"}\n```')
        self.assertEqual(json.loads(r), {"k": "v"})

    def test_preamble(self):
        r = extract_json_block('Analysis:\n\n{"severity": "high"}')
        self.assertEqual(json.loads(r)["severity"], "high")


class TestParseLlmJson(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_llm_json('{"a": 1}'), {"a": 1})

    def test_fallback(self):
        fb = {"a": 0}
        self.assertEqual(parse_llm_json("bad", fallback=fb), fb)

    def test_raises_without_fallback(self):
        with self.assertRaises(ValueError):
            parse_llm_json("bad")


# ══════════════════════════════════════════════════════════════════════════
# UTILS — SERIALIZATION
# ══════════════════════════════════════════════════════════════════════════

class TestSerialization(unittest.TestCase):
    def _make_result(self):
        f = RegulatoryFiling(
            id="T-001", title="Test", domain=RegulatoryDomain.SEC,
            source_url="https://x.com", published_date="2026-01-01",
            raw_text="text", change_type=ChangeType.FINAL_RULE,
        )
        i = ImpactAssessment(
            filing_id="T-001", severity=Severity.CRITICAL,
            affected_business_lines=["Eq"], affected_regulations=["Reg"],
            compliance_deadline="2026-12-15", action_items=["Do it"],
            risk_summary="Risk", confidence=0.95,
        )
        d = DecisionFrame(
            decision_id="decision::T-001", question="What action is warranted?", scope="SEC review", time_horizon="near-term",
            affected_entities=["Eq"], candidate_actions=["Escalate"], constraints=["Legal review required"],
            evidence_items=["Source filing"], assumptions=["No implementation delay"], counterarguments=["Scope may narrow"],
            confidence=0.9, expected_revisit_date="2026-12-01", owner="Compliance", audit_refs=["T-001"]
        )
        e = EvidenceLedgerEntry(evidence_id="episodic:T-001", source_type="episodic", supports=["Escalate"], contradicts=[], strength_score=0.9, novelty_score=0.4, trace=["memory_id=episodic:T-001"], summary="Test evidence")
        return MonitorResult(filing=f, impact=i, decision=d, evidence_ledger=[e], raw_analysis="{}")

    def test_enum_serializer(self):
        self.assertEqual(enum_serializer(Severity.HIGH), "high")

    def test_serialize_result_enums_resolved(self):
        sr = serialize_result(self._make_result())
        self.assertEqual(sr["filing"]["domain"], "sec")
        self.assertEqual(sr["impact"]["severity"], "critical")
        self.assertEqual(sr["decision"]["decision_id"], "decision::T-001")
        self.assertEqual(sr["evidence_ledger"][0]["evidence_id"], "episodic:T-001")
        json.dumps(sr)  # should not raise


# ══════════════════════════════════════════════════════════════════════════
# FETCHERS
# ══════════════════════════════════════════════════════════════════════════

class TestSampleData(unittest.TestCase):
    def test_not_empty(self):
        self.assertGreaterEqual(len(SAMPLE_FILINGS), 6)

    def test_required_fields(self):
        req = {"id", "title", "domain", "source_url", "published_date", "change_type", "raw_text"}
        for f in SAMPLE_FILINGS:
            self.assertTrue(req <= set(f.keys()), f"Missing in {f['id']}")

    def test_all_have_mock_analyses(self):
        for f in SAMPLE_FILINGS:
            self.assertIn(f["id"], MOCK_ANALYSES)


class TestFetchFilings(unittest.TestCase):
    def test_fetch_all(self):
        self.assertEqual(len(fetch_filings(since_days=365)), len(SAMPLE_FILINGS))

    def test_domain_filter(self):
        sec = fetch_filings(domains=[RegulatoryDomain.SEC], since_days=365)
        self.assertTrue(all(f.domain == RegulatoryDomain.SEC for f in sec))

    def test_since_days(self):
        recent = fetch_filings(since_days=1)
        all_f = fetch_filings(since_days=365)
        self.assertLessEqual(len(recent), len(all_f))


class TestDomainBusinessLines(unittest.TestCase):
    def test_all_covered(self):
        for d in RegulatoryDomain:
            self.assertIn(d.value, DOMAIN_BUSINESS_LINES)


# ══════════════════════════════════════════════════════════════════════════
# PROVIDERS
# ══════════════════════════════════════════════════════════════════════════

class TestMockProvider(unittest.TestCase):
    def test_known_filing(self):
        p = MockProvider()
        r = json.loads(p.complete("sys", "FILING ID: SEC-2026-0312-A\ntext"))
        self.assertEqual(r["severity"], "critical")

    def test_unknown_filing(self):
        p = MockProvider()
        r = json.loads(p.complete("sys", "FILING ID: UNKNOWN-999\ntext"))
        self.assertEqual(r["severity"], "low")

    def test_name(self):
        self.assertEqual(MockProvider().name(), "MockProvider/demo")


class TestBuildProvider(unittest.TestCase):
    def test_mock(self):
        self.assertIsInstance(build_provider("mock"), MockProvider)

    def test_unknown_raises(self):
        with self.assertRaises(ValueError):
            build_provider("bogus")


# ══════════════════════════════════════════════════════════════════════════
# MEMORY
# ══════════════════════════════════════════════════════════════════════════

class TestMemoryStore(unittest.TestCase):
    def setUp(self):
        self.mem = MemoryStore(":memory:")

    def tearDown(self):
        self.mem.close()

    def test_empty(self):
        self.assertEqual(self.mem.count(), 0)

    def test_store_episodic(self):
        self.mem.store_episodic("T-001", {"title": "A", "domain": "sec"}, {"severity": "high", "affected_business_lines": ["Eq"], "affected_regulations": ["R"], "risk_summary": "X"})
        self.assertEqual(self.mem.count(MemoryType.EPISODIC), 1)

    def test_store_entity(self):
        self.mem.store_entity("Reg S-K", {"type": "regulation"})
        self.assertEqual(self.mem.count(MemoryType.ENTITY), 1)

    def test_feedback(self):
        self.mem.store_episodic("T-001", {"title": "A"}, {"severity": "med"})
        self.mem.record_feedback("T-001", "severity", "med", "high", "reason")
        self.assertEqual(self.mem.count(MemoryType.PRECEDENT), 1)
        self.assertEqual(self.mem.stats()["total_feedback"], 1)

    def test_get_by_id(self):
        self.mem.store_episodic("T-001", {"title": "A"}, {"severity": "high"})
        r = self.mem.get("episodic:T-001")
        self.assertIsNotNone(r)
        self.assertEqual(r.key, "T-001")

    def test_get_nonexistent(self):
        self.assertIsNone(self.mem.get("nope:123"))

    def test_recall_semantic(self):
        self.mem.store_episodic("SEC-001", {"title": "Climate", "domain": "sec"}, {"severity": "high", "affected_business_lines": ["ESG"], "affected_regulations": [], "risk_summary": "SEC"})
        self.mem.store_episodic("FDA-001", {"title": "Device AI", "domain": "fda"}, {"severity": "med", "affected_business_lines": ["Dev"], "affected_regulations": [], "risk_summary": "FDA"})
        results = self.mem.recall("climate SEC ESG", top_k=2)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].key, "SEC-001")

    def test_recall_type_filter(self):
        self.mem.store_episodic("T-001", {"title": "A"}, {"severity": "high"})
        self.mem.record_feedback("T-001", "severity", "high", "critical", "r")
        eps = self.mem.recall("test", top_k=5, memory_type=MemoryType.EPISODIC)
        self.assertTrue(all(r.memory_type == MemoryType.EPISODIC for r in eps))

    def test_filing_history(self):
        self.mem.store_episodic("SEC-001", {"title": "A", "domain": "sec"}, {"severity": "h"})
        self.mem.store_episodic("FDA-001", {"title": "B", "domain": "fda"}, {"severity": "l"})
        self.assertEqual(len(self.mem.get_filing_history()), 2)
        self.assertEqual(len(self.mem.get_filing_history(domain="sec")), 1)

    def test_entity_relations_auto_created(self):
        self.mem.store_episodic("T-001", {"title": "A", "domain": "sec"}, {"severity": "h", "affected_business_lines": ["Eq"], "affected_regulations": ["Reg"], "risk_summary": "R"})
        self.assertGreater(len(self.mem.get_related_entities("Reg")), 0)

    def test_context_block_empty(self):
        self.assertEqual(self.mem.build_context_block("sec", "text"), "")

    def test_context_block_with_data(self):
        self.mem.store_episodic("SEC-001", {"id": "SEC-001", "title": "Climate", "domain": "sec"}, {"severity": "critical", "affected_business_lines": ["ESG"], "affected_regulations": [], "risk_summary": "R"})
        ctx = self.mem.build_context_block("sec", "climate disclosure")
        self.assertIn("WEIGHTED EVIDENCE LEDGER", ctx)
        self.assertIn("RELEVANT PAST ANALYSES", ctx)
        self.assertIn("SEC-001", ctx)

    def test_context_block_with_precedents(self):
        self.mem.store_episodic("T-001", {"title": "A", "domain": "sec"}, {"severity": "med"})
        self.mem.record_feedback("T-001", "severity", "med", "critical", "important")
        ctx = self.mem.build_context_block("sec", "regulatory correction important")
        self.assertIn("CORRECTION PRECEDENTS", ctx)

    def test_export_import(self):
        self.mem.store_episodic("T-001", {"title": "A"}, {"severity": "high"})
        self.mem.record_feedback("T-001", "severity", "high", "critical", "r")
        exported = self.mem.export_json()
        data = json.loads(exported)
        self.assertEqual(len(data["memories"]), 2)

        fresh = MemoryStore(":memory:")
        fresh.import_json(exported)
        self.assertEqual(fresh.count(), 2)
        fresh.close()


class TestSimilarityEngine(unittest.TestCase):
    def test_index_and_search(self):
        e = SimilarityEngine()
        e.index({"d1": "climate SEC emissions", "d2": "medical device FDA AI", "d3": "tariff semiconductor China"})
        results = e.search("climate SEC", top_k=2)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0], "d1")

    def test_empty(self):
        e = SimilarityEngine()
        self.assertEqual(e.search("anything"), [])

    def test_backend(self):
        self.assertIn(SimilarityEngine().backend, ("sklearn", "keyword"))


# ══════════════════════════════════════════════════════════════════════════
# AGENT
# ══════════════════════════════════════════════════════════════════════════

class TestAgent(unittest.TestCase):
    def setUp(self):
        self.mem = MemoryStore(":memory:")
        self.tmpdir = tempfile.mkdtemp()
        self.agent = RegulatoryMonitorAgent(
            provider=MockProvider(),
            memory=self.mem,
            state_path=os.path.join(self.tmpdir, "state.json"),
        )
        self.agent.reset_state()

    def tearDown(self):
        self.mem.close()

    def test_run_returns_results(self):
        results = self.agent.run(since_days=90)
        self.assertEqual(len(results), len(fetch_filings(since_days=90)))

    def test_result_structure(self):
        results = self.agent.run(since_days=90)
        for r in results:
            self.assertTrue(r.filing.id)
            self.assertEqual(r.impact.filing_id, r.filing.id)
            self.assertIn(r.impact.severity, Severity)
            self.assertGreaterEqual(r.impact.confidence, 0.0)
            self.assertLessEqual(r.impact.confidence, 1.0)
            self.assertGreater(len(r.impact.action_items), 0)
            self.assertTrue(r.decision.decision_id)
            self.assertEqual(r.decision.audit_refs[0], r.filing.id)
            self.assertIsInstance(r.evidence_ledger, list)

    def test_deduplication(self):
        first = self.agent.run(since_days=90)
        second = self.agent.run(since_days=90)
        self.assertEqual(len(first), len(fetch_filings(since_days=90)))
        self.assertEqual(len(second), 0)

    def test_reset_state(self):
        self.agent.run(since_days=90)
        self.agent.reset_state()
        self.assertEqual(len(self.agent.run(since_days=90)), len(fetch_filings(since_days=90)))

    def test_domain_filter(self):
        self.agent.domains = [RegulatoryDomain.SEC, RegulatoryDomain.FDA]
        results = self.agent.run(since_days=90)
        domains = {r.filing.domain for r in results}
        self.assertTrue(domains <= {RegulatoryDomain.SEC, RegulatoryDomain.FDA})

    def test_run_json_valid(self):
        output = self.agent.run_json(since_days=90)
        data = json.loads(output)
        self.assertEqual(len(data), len(fetch_filings(since_days=90)))
        for item in data:
            self.assertIsInstance(item["filing"]["domain"], str)
            self.assertIsInstance(item["impact"]["severity"], str)

    def test_memory_populated(self):
        self.agent.run(since_days=90)
        self.assertEqual(self.mem.count(MemoryType.EPISODIC), len(fetch_filings(since_days=90)))
        self.assertGreater(self.mem.stats()["total_relations"], 0)

    def test_agent_without_memory(self):
        agent = RegulatoryMonitorAgent(
            provider=MockProvider(), memory=None,
            state_path=os.path.join(self.tmpdir, "state2.json"),
        )
        results = agent.run(since_days=90)
        self.assertEqual(len(results), len(fetch_filings(since_days=90)))


# ══════════════════════════════════════════════════════════════════════════
# MCP STANDALONE
# ══════════════════════════════════════════════════════════════════════════

class TestMCPStandalone(unittest.TestCase):
    def setUp(self):
        self.mem = MemoryStore(":memory:")
        self.mem.store_episodic(
            "SEC-001",
            {"id": "SEC-001", "title": "Climate Rule", "domain": "sec", "summary": "SEC climate."},
            {"severity": "critical", "affected_business_lines": ["ESG"], "affected_regulations": ["Reg S-K"], "risk_summary": "Risk"},
        )
        self.mem.record_feedback("SEC-001", "severity", "critical", "critical", "confirmed")

        import naturalsentinel.mcp.server as mcp_mod
        mcp_mod._memory = self.mem
        from naturalsentinel.mcp.server import StandaloneServer
        self.server = StandaloneServer()

    def tearDown(self):
        self.mem.close()

    def test_tools_list(self):
        resp = self.server.handle_request({"method": "tools/list", "params": {}})
        self.assertIn("tools", resp)
        self.assertGreaterEqual(len(resp["tools"]), 4)

    def test_memory_stats(self):
        resp = self.server.handle_request({"method": "tools/call", "params": {"name": "get_memory_stats", "arguments": {}}})
        self.assertIn("total_memories", resp["result"])

    def test_recall(self):
        resp = self.server.handle_request({"method": "tools/call", "params": {"name": "recall_memory", "arguments": {"query": "climate SEC", "top_k": 2}}})
        self.assertGreater(len(resp["result"]), 0)

    def test_feedback(self):
        resp = self.server.handle_request({"method": "tools/call", "params": {"name": "provide_feedback", "arguments": {"filing_id": "SEC-001", "field": "severity", "old_value": "high", "new_value": "critical", "reason": "test"}}})
        self.assertEqual(resp["result"]["status"], "recorded")

    def test_entity_relations(self):
        resp = self.server.handle_request({"method": "tools/call", "params": {"name": "get_entity_relations", "arguments": {"entity": "Reg S-K"}}})
        self.assertIsInstance(resp["result"], list)

    def test_unknown_tool(self):
        resp = self.server.handle_request({"method": "tools/call", "params": {"name": "bogus", "arguments": {}}})
        self.assertIn("error", resp)

    def test_resources_list(self):
        resp = self.server.handle_request({"method": "resources/list", "params": {}})
        self.assertIn("naturalsentinel://memory/stats", resp["resources"])

    def test_read_config(self):
        resp = self.server.handle_request({"method": "resources/read", "params": {"uri": "naturalsentinel://config/domains"}})
        self.assertIn("domains", resp["result"])

    def test_unknown_method(self):
        resp = self.server.handle_request({"method": "bogus", "params": {}})
        self.assertIn("error", resp)


if __name__ == "__main__":
    unittest.main()
