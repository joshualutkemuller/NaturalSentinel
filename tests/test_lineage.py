"""Tests for the data lineage and explainability layer.

Covers:
- FieldCitation / CitationBundle: construction, get, as_flat_dict, to_dict
- parse_citations: from LLM response dict with and without citations key
- DecisionTrace / TraceStep: start, step context manager, finish, timing
- ModelProvenance: from_context, hash_prompt, unknown(), to_dict
- MemoryStore decision_traces CRUD: store, retrieve, get_traces_for_filing
- MemoryStore citations CRUD: store, retrieve
- AnalyzeFilingSkill integration: verify trace_id, citations, provenance,
  audit events, and escalation_reasons in result
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from naturalsentinel.lineage.citation import (
    CITABLE_FIELDS,
    CitationBundle,
    FieldCitation,
    parse_citations,
)
from naturalsentinel.lineage.provenance import ModelProvenance
from naturalsentinel.lineage.trace import DecisionTrace
from naturalsentinel.memory.store import MemoryStore
from naturalsentinel.skills.analyze import AnalyzeFilingSkill


def make_mem():
    return MemoryStore(":memory:")


# ---------------------------------------------------------------------------
# FieldCitation
# ---------------------------------------------------------------------------


class TestFieldCitation(unittest.TestCase):
    def test_to_dict_has_required_keys(self):
        cit = FieldCitation(
            field="severity",
            value="high",
            source_passage="The rule takes immediate effect.",
            source_url="https://example.com/rule",
            confidence=0.85,
        )
        d = cit.to_dict()
        self.assertEqual(d["field"], "severity")
        self.assertEqual(d["value"], "high")
        self.assertEqual(d["source_passage"], "The rule takes immediate effect.")
        self.assertAlmostEqual(d["confidence"], 0.85)

    def test_section_hint_optional(self):
        cit = FieldCitation("severity", "high", "passage", "https://x.com")
        self.assertEqual(cit.section_hint, "")


# ---------------------------------------------------------------------------
# CitationBundle
# ---------------------------------------------------------------------------


class TestCitationBundle(unittest.TestCase):
    def _make_bundle(self):
        return CitationBundle(
            filing_id="SEC-001",
            source_url="https://example.com",
            citations=[
                FieldCitation(
                    "severity", "high", "immediate effect", "https://example.com", confidence=0.9
                ),
                FieldCitation(
                    "change_type",
                    "final_rule",
                    "final rule adopted",
                    "https://example.com",
                    confidence=0.95,
                ),
                FieldCitation(
                    "compliance_deadline",
                    "2026-12-31",
                    "by year end",
                    "https://example.com",
                    confidence=0.8,
                ),
            ],
        )

    def test_get_existing_field(self):
        bundle = self._make_bundle()
        cit = bundle.get("severity")
        self.assertIsNotNone(cit)
        self.assertEqual(cit.field, "severity")

    def test_get_missing_field_returns_none(self):
        bundle = self._make_bundle()
        self.assertIsNone(bundle.get("nonexistent_field"))

    def test_as_flat_dict(self):
        bundle = self._make_bundle()
        flat = bundle.as_flat_dict()
        self.assertIn("severity", flat)
        self.assertEqual(flat["severity"], "immediate effect")

    def test_to_dict_structure(self):
        d = self._make_bundle().to_dict()
        self.assertEqual(d["filing_id"], "SEC-001")
        self.assertIsInstance(d["citations"], list)
        self.assertEqual(len(d["citations"]), 3)

    def test_empty_bundle(self):
        bundle = CitationBundle("X", "")
        self.assertEqual(bundle.as_flat_dict(), {})
        self.assertIsNone(bundle.get("severity"))


# ---------------------------------------------------------------------------
# parse_citations
# ---------------------------------------------------------------------------


class TestParseCitations(unittest.TestCase):
    def test_parses_citations_from_llm_response(self):
        parsed = {
            "severity": "high",
            "confidence": 0.85,
            "citations": {
                "severity": "All covered entities must comply within 30 days.",
                "change_type": "The Commission is adopting final rules.",
            },
        }
        bundle = parse_citations(parsed, filing_id="SEC-001", source_url="https://sec.gov")
        self.assertEqual(len(bundle.citations), 2)
        self.assertIsNotNone(bundle.get("severity"))
        self.assertEqual(
            bundle.get("severity").source_passage,
            "All covered entities must comply within 30 days.",
        )

    def test_empty_citations_key_returns_empty_bundle(self):
        parsed = {"severity": "medium", "confidence": 0.6, "citations": {}}
        bundle = parse_citations(parsed, filing_id="X")
        self.assertEqual(len(bundle.citations), 0)

    def test_missing_citations_key_returns_empty_bundle(self):
        parsed = {"severity": "medium", "confidence": 0.6}
        bundle = parse_citations(parsed, filing_id="X")
        self.assertEqual(len(bundle.citations), 0)

    def test_confidence_from_overall_when_no_field_confidence(self):
        parsed = {
            "confidence": 0.77,
            "citations": {"severity": "some passage"},
        }
        bundle = parse_citations(parsed, filing_id="X", overall_confidence=0.77)
        cit = bundle.get("severity")
        self.assertAlmostEqual(cit.confidence, 0.77)

    def test_filing_id_and_source_url_preserved(self):
        parsed = {"citations": {"severity": "passage"}}
        bundle = parse_citations(parsed, filing_id="MY-001", source_url="https://fed.gov")
        self.assertEqual(bundle.filing_id, "MY-001")
        self.assertEqual(bundle.source_url, "https://fed.gov")
        self.assertEqual(bundle.get("severity").source_url, "https://fed.gov")

    def test_non_string_citations_skipped(self):
        parsed = {"citations": {"severity": None, "change_type": ["not", "a", "string"]}}
        bundle = parse_citations(parsed, filing_id="X")
        self.assertEqual(len(bundle.citations), 0)

    def test_citable_fields_set_not_empty(self):
        self.assertGreater(len(CITABLE_FIELDS), 0)
        self.assertIn("severity", CITABLE_FIELDS)


# ---------------------------------------------------------------------------
# DecisionTrace
# ---------------------------------------------------------------------------


class TestDecisionTrace(unittest.TestCase):
    def test_start_creates_trace(self):
        trace = DecisionTrace.start("F-001")
        self.assertEqual(trace.filing_id, "F-001")
        self.assertIsNotNone(trace.trace_id)
        self.assertIsNotNone(trace.started_at)

    def test_custom_trace_id(self):
        trace = DecisionTrace.start("F-001", trace_id="my-trace-id")
        self.assertEqual(trace.trace_id, "my-trace-id")

    def test_step_context_manager_records_step(self):
        trace = DecisionTrace.start("F-001")
        with trace.step("build_prompt", "input=hello") as s:
            s.output_summary = "output=world"
        self.assertEqual(len(trace.steps), 1)
        step = trace.steps[0]
        self.assertEqual(step.step_name, "build_prompt")
        self.assertEqual(step.input_summary, "input=hello")
        self.assertEqual(step.output_summary, "output=world")
        self.assertEqual(step.status, "ok")
        self.assertGreaterEqual(step.duration_ms, 0)

    def test_step_records_duration(self):
        trace = DecisionTrace.start("F-001")
        with trace.step("slow_step") as _s:
            time.sleep(0.01)
        self.assertGreater(trace.steps[0].duration_ms, 5)

    def test_step_error_sets_status(self):
        trace = DecisionTrace.start("F-001")
        try:
            with trace.step("failing_step") as _s:
                raise ValueError("test error")
        except ValueError:
            pass
        self.assertEqual(trace.steps[0].status, "error")
        self.assertIn("ValueError", trace.steps[0].notes)

    def test_finish_computes_totals(self):
        trace = DecisionTrace.start("F-001")
        with trace.step("step1") as s:
            s.token_usage = 100
        with trace.step("step2") as s:
            s.token_usage = 200
        trace.finish()
        self.assertEqual(trace.total_tokens, 300)
        self.assertGreater(trace.total_duration_ms, 0)
        self.assertEqual(trace.overall_status, "ok")

    def test_finish_overall_status_error_if_any_step_failed(self):
        trace = DecisionTrace.start("F-001")
        with trace.step("ok_step"):
            pass
        try:
            with trace.step("bad_step"):
                raise RuntimeError("oops")
        except RuntimeError:
            pass
        trace.finish()
        self.assertEqual(trace.overall_status, "error")

    def test_to_dict_structure(self):
        trace = DecisionTrace.start("F-001")
        with trace.step("s1"):
            pass
        trace.finish()
        d = trace.to_dict()
        self.assertIn("trace_id", d)
        self.assertIn("filing_id", d)
        self.assertIn("steps", d)
        self.assertEqual(len(d["steps"]), 1)

    def test_multiple_steps(self):
        trace = DecisionTrace.start("F-001")
        for name in ["a", "b", "c"]:
            with trace.step(name):
                pass
        self.assertEqual(len(trace.steps), 3)


# ---------------------------------------------------------------------------
# ModelProvenance
# ---------------------------------------------------------------------------


class TestModelProvenance(unittest.TestCase):
    class FakeLLM:
        provider = "anthropic"
        model = "claude-sonnet-4-6"
        model_version = "2026-03-01"

    class FakeContext:
        llm = None

    def test_hash_prompt_is_16_chars(self):
        h = ModelProvenance.hash_prompt("Hello world")
        self.assertEqual(len(h), 16)

    def test_same_prompt_same_hash(self):
        h1 = ModelProvenance.hash_prompt("template")
        h2 = ModelProvenance.hash_prompt("template")
        self.assertEqual(h1, h2)

    def test_different_prompt_different_hash(self):
        h1 = ModelProvenance.hash_prompt("template A")
        h2 = ModelProvenance.hash_prompt("template B")
        self.assertNotEqual(h1, h2)

    def test_from_context_with_llm(self):
        ctx = self.FakeContext()
        ctx.llm = self.FakeLLM()
        prov = ModelProvenance.from_context(ctx, prompt_template="sys prompt")
        self.assertEqual(prov.provider, "anthropic")
        self.assertEqual(prov.model, "claude-sonnet-4-6")
        self.assertEqual(len(prov.prompt_template_hash), 16)

    def test_from_context_no_llm(self):
        ctx = self.FakeContext()
        prov = ModelProvenance.from_context(ctx)
        self.assertEqual(prov.provider, "unknown")
        self.assertEqual(prov.model, "unknown")

    def test_unknown_factory(self):
        prov = ModelProvenance.unknown()
        self.assertEqual(prov.provider, "unknown")
        self.assertEqual(prov.max_tokens, 0)

    def test_to_dict_has_all_fields(self):
        prov = ModelProvenance.unknown()
        d = prov.to_dict()
        for key in (
            "provider",
            "model",
            "model_version",
            "temperature",
            "max_tokens",
            "prompt_template_hash",
        ):
            self.assertIn(key, d)


# ---------------------------------------------------------------------------
# MemoryStore decision_traces and citations CRUD
# ---------------------------------------------------------------------------


class TestMemoryStoreTraces(unittest.TestCase):
    def setUp(self):
        self.mem = make_mem()

    def tearDown(self):
        self.mem.close()

    def _make_trace(self, filing_id="F-001"):
        trace = DecisionTrace.start(filing_id=filing_id)
        with trace.step("build_prompt") as s:
            s.token_usage = 100
        with trace.step("llm_inference") as s:
            s.token_usage = 300
            s.provider = "anthropic"
            s.model = "claude-sonnet-4-6"
        trace.finish()
        return trace

    def test_store_and_retrieve_trace(self):
        trace = self._make_trace()
        self.mem.store_decision_trace(trace)
        retrieved = self.mem.get_decision_trace(trace.trace_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["filing_id"], "F-001")
        self.assertEqual(retrieved["total_tokens"], 400)
        self.assertEqual(len(retrieved["steps"]), 2)

    def test_get_nonexistent_trace_returns_none(self):
        self.assertIsNone(self.mem.get_decision_trace("ghost-trace-id"))

    def test_get_traces_for_filing(self):
        t1 = self._make_trace("F-001")
        t2 = self._make_trace("F-001")
        t3 = self._make_trace("F-002")
        for t in (t1, t2, t3):
            self.mem.store_decision_trace(t)
        traces = self.mem.get_traces_for_filing("F-001")
        self.assertEqual(len(traces), 2)

    def test_steps_deserialised(self):
        trace = self._make_trace()
        self.mem.store_decision_trace(trace)
        r = self.mem.get_decision_trace(trace.trace_id)
        self.assertIsInstance(r["steps"], list)
        self.assertEqual(r["steps"][0]["step_name"], "build_prompt")

    def test_upsert_overwrites_trace(self):
        trace = self._make_trace()
        self.mem.store_decision_trace(trace)
        trace.overall_status = "warning"
        self.mem.store_decision_trace(trace)
        r = self.mem.get_decision_trace(trace.trace_id)
        self.assertEqual(r["overall_status"], "warning")


class TestMemoryStoreCitations(unittest.TestCase):
    def setUp(self):
        self.mem = make_mem()

    def tearDown(self):
        self.mem.close()

    def _make_bundle(self, filing_id="F-001"):
        return CitationBundle(
            filing_id=filing_id,
            source_url="https://example.com",
            citations=[
                FieldCitation("severity", "high", "passage A", "https://example.com"),
                FieldCitation("change_type", "final_rule", "passage B", "https://example.com"),
            ],
        )

    def test_store_and_retrieve_citations(self):
        bundle = self._make_bundle()
        self.mem.store_citations(bundle)
        r = self.mem.get_citations("F-001")
        self.assertIsNotNone(r)
        self.assertEqual(r["filing_id"], "F-001")
        self.assertEqual(len(r["citations"]), 2)

    def test_get_nonexistent_filing_returns_none(self):
        self.assertIsNone(self.mem.get_citations("ghost-filing"))

    def test_citations_deserialised(self):
        bundle = self._make_bundle()
        self.mem.store_citations(bundle)
        r = self.mem.get_citations("F-001")
        first = r["citations"][0]
        self.assertIn("field", first)
        self.assertIn("source_passage", first)

    def test_upsert_overwrites_citations(self):
        bundle = self._make_bundle()
        self.mem.store_citations(bundle)
        # Replace with single citation
        bundle2 = CitationBundle(
            "F-001",
            "https://example.com",
            citations=[
                FieldCitation("severity", "low", "updated passage", "https://example.com"),
            ],
        )
        self.mem.store_citations(bundle2)
        r = self.mem.get_citations("F-001")
        self.assertEqual(len(r["citations"]), 1)
        self.assertEqual(r["citations"][0]["value"], "low")


# ---------------------------------------------------------------------------
# AnalyzeFilingSkill integration — lineage and governance wiring
# ---------------------------------------------------------------------------


class FakeLLM:
    provider = "anthropic"
    model = "claude-sonnet-4-6"
    model_version = ""

    def complete(self, system, user, temperature=0.1):
        return """{
            "summary": "A final rule on capital requirements.",
            "change_type": "final_rule",
            "severity": "high",
            "affected_business_lines": ["Commercial Banking"],
            "affected_regulations": ["Basel IV"],
            "compliance_deadline": "2026-12-31",
            "action_items": ["Update RWA models"],
            "risk_summary": "Failure to comply risks regulatory sanctions.",
            "confidence": 0.82,
            "citations": {
                "severity": "All institutions must comply immediately.",
                "change_type": "The Committee is issuing final standards.",
                "compliance_deadline": "Deadline is 31 December 2026."
            },
            "decision": {
                "decision_id": "d-001",
                "question": "How do we comply?",
                "scope": "Capital",
                "time_horizon": "near-term",
                "affected_entities": ["Risk"],
                "candidate_actions": ["Model update"],
                "constraints": [],
                "evidence_items": [],
                "assumptions": [],
                "counterarguments": [],
                "confidence": 0.80,
                "expected_revisit_date": null,
                "owner": "Risk",
                "audit_refs": []
            }
        }"""


class FakeContext:
    def __init__(self, memory=None, params=None):
        self.llm = FakeLLM()
        self.memory = memory
        self.params = params or {}


class TestAnalyzeFilingSkillLineage(unittest.TestCase):
    def setUp(self):
        self.mem = make_mem()
        self.skill = AnalyzeFilingSkill()

    def tearDown(self):
        self.mem.close()

    def _ctx(self, **extra_params):
        params = {
            "filing": {
                "id": "FED-001",
                "title": "Capital Requirements Final Rule",
                "domain": "fed",
                "published_date": "2026-03-15",
                "source_url": "https://fed.gov/rule",
                "raw_text": "All institutions must comply immediately.",
            },
            "memory_context": "",
        }
        params.update(extra_params)
        return FakeContext(memory=self.mem, params=params)

    def test_result_contains_trace_id(self):
        result = self.skill.execute(self._ctx())
        self.assertTrue(result.success)
        self.assertIn("trace_id", result.data)
        self.assertIsNotNone(result.data["trace_id"])

    def test_result_contains_citations(self):
        result = self.skill.execute(self._ctx())
        self.assertIn("citations", result.data)
        citations = result.data["citations"]
        self.assertIsInstance(citations, dict)
        self.assertIn("severity", citations)

    def test_result_contains_provenance(self):
        result = self.skill.execute(self._ctx())
        self.assertIn("provenance", result.data)
        prov = result.data["provenance"]
        self.assertEqual(prov["provider"], "anthropic")
        self.assertEqual(prov["model"], "claude-sonnet-4-6")

    def test_trace_stored_in_memory(self):
        result = self.skill.execute(self._ctx())
        trace_id = result.data["trace_id"]
        trace = self.mem.get_decision_trace(trace_id)
        self.assertIsNotNone(trace)
        self.assertEqual(trace["filing_id"], "FED-001")

    def test_citations_stored_in_memory(self):
        self.skill.execute(self._ctx())
        stored = self.mem.get_citations("FED-001")
        self.assertIsNotNone(stored)
        self.assertGreater(len(stored["citations"]), 0)

    def test_audit_event_emitted(self):
        self.skill.execute(self._ctx())
        events = self.mem.get_audit_events(event_type="ANALYSIS_COMPLETED")
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["filing_id"], "FED-001")
        self.assertIn("severity", ev["payload"])

    def test_no_escalation_on_normal_assessment(self):
        result = self.skill.execute(self._ctx())
        self.assertEqual(result.data.get("escalation_reasons"), [])
        # No ESCALATION_TRIGGERED event
        escalations = self.mem.get_audit_events(event_type="ESCALATION_TRIGGERED")
        self.assertEqual(len(escalations), 0)

    def test_escalation_triggered_for_critical_severity(self):
        class CriticalFakeLLM(FakeLLM):
            def complete(self, system, user, temperature=0.1):

                return (
                    super()
                    .complete(system, user, temperature)
                    .replace('"severity": "high"', '"severity": "critical"')
                    .replace('"confidence": 0.82', '"confidence": 0.10')
                )

        ctx = self._ctx()
        ctx.llm = CriticalFakeLLM()
        result = self.skill.execute(ctx)
        self.assertGreater(len(result.data.get("escalation_reasons", [])), 0)
        escalations = self.mem.get_audit_events(event_type="ESCALATION_TRIGGERED")
        self.assertGreater(len(escalations), 0)

    def test_metadata_contains_n_citations(self):
        result = self.skill.execute(self._ctx())
        self.assertIn("n_citations", result.metadata)
        self.assertGreater(result.metadata["n_citations"], 0)

    def test_llm_denied_returns_failure(self):
        ctx = FakeContext(
            memory=self.mem,
            params={
                "filing": {"id": "X", "domain": "sec", "raw_text": "test"},
            },
        )
        ctx.llm = None
        result = self.skill.execute(ctx)
        self.assertFalse(result.success)

    def test_llm_exception_returns_failure_and_audit_event(self):
        class ErrorLLM(FakeLLM):
            def complete(self, *a, **kw):
                raise RuntimeError("provider down")

        ctx = self._ctx()
        ctx.llm = ErrorLLM()
        result = self.skill.execute(ctx)
        self.assertFalse(result.success)
        failed_events = self.mem.get_audit_events(event_type="ANALYSIS_FAILED")
        self.assertEqual(len(failed_events), 1)


if __name__ == "__main__":
    unittest.main()
