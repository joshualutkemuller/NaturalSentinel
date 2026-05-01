"""Tests for the governance artifacts layer.

Covers:
- ModelCard: construction, validation, to_dict, from_json
- ControlMatrix: construction, filtering, coverage_summary, to_dict
- AuditEvent: creation, to_dict, severity_for_event
- FailureTaxonomy: all codes present, auto_escalate_codes, classify
- FailureRecord: creation, to_dict
- EscalationPolicy: evaluate across all trigger types, from_dict
- FallbackPolicy: select for each failure code, cache age logic, from_dict
- MemoryStore audit_log CRUD: emit_audit_event, get_audit_events (with filters)
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.naturalsentinel.governance.audit import (
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    severity_for_event,
)
from app.naturalsentinel.governance.control_matrix import Control, ControlMatrix
from app.naturalsentinel.governance.failure_taxonomy import (
    FAILURE_TAXONOMY,
    FailureRecord,
    auto_escalate_codes,
)
from app.naturalsentinel.governance.failure_taxonomy import (
    classify as classify_failure,
)
from app.naturalsentinel.governance.model_card import ModelCard
from app.naturalsentinel.governance.policy import (
    FALLBACK_ACTIONS,
    EscalationPolicy,
    FallbackPolicy,
)
from app.naturalsentinel.memory.store import MemoryStore


def make_mem():
    return MemoryStore(":memory:")


# ---------------------------------------------------------------------------
# ModelCard
# ---------------------------------------------------------------------------


class TestModelCard(unittest.TestCase):
    def test_default_returns_card(self):
        card = ModelCard.default()
        self.assertIsInstance(card, ModelCard)
        self.assertEqual(card.name, "NaturalSentinel Regulatory Extraction Pipeline")

    def test_to_dict_contains_all_fields(self):
        d = ModelCard.default().to_dict()
        required = [
            "name",
            "version",
            "provider",
            "model_id",
            "intended_use",
            "intended_users",
            "out_of_scope_uses",
            "known_limitations",
            "ethical_considerations",
            "evaluated_domains",
            "evaluation_metrics",
            "contact",
            "license",
        ]
        for field in required:
            self.assertIn(field, d, f"Missing key: {field}")

    def test_validate_complete_card_has_no_warnings(self):
        card = ModelCard.default()
        card.evaluation_metrics = {"overall_accuracy": 0.82}
        card.contact = "test@example.com"
        card.intended_use = "Test"
        card.known_limitations = ["one limitation"]
        card.out_of_scope_uses = ["one out-of-scope use"]
        card.ethical_considerations = ["one ethical consideration"]
        card.last_reviewed = "2026-03-18"
        warnings = card.validate()
        self.assertEqual(warnings, [])

    def test_validate_flags_missing_fields(self):
        card = ModelCard.default()
        card.intended_use = ""
        card.known_limitations = []
        card.evaluation_metrics = {}
        warnings = card.validate()
        self.assertTrue(any("intended_use" in w for w in warnings))
        self.assertTrue(any("known_limitations" in w for w in warnings))
        self.assertTrue(any("evaluation_metrics" in w for w in warnings))

    def test_from_json_loads_and_merges(self):
        data = {
            "name": "Custom Card",
            "version": "2.0.0",
            "evaluation_metrics": {"overall_accuracy": 0.85},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            json.dump(data, fh)
            fh_name = fh.name
        try:
            card = ModelCard.from_json(fh_name)
            self.assertEqual(card.name, "Custom Card")
            self.assertEqual(card.version, "2.0.0")
            # Defaults should still be present
            self.assertIn("anthropic", card.provider)
        finally:
            os.unlink(fh_name)

    def test_model_card_json_asset_is_valid(self):
        # Test moved into governance/ subdir — went from .../tests/naturalsentinel/
        # to .../tests/naturalsentinel/governance/, so we need one more "..".
        asset_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "..",
            "assets",
            "model_card.json",
        )
        card = ModelCard.from_json(asset_path)
        self.assertEqual(card.name, "NaturalSentinel Regulatory Extraction Pipeline")
        self.assertGreater(len(card.known_limitations), 0)


# ---------------------------------------------------------------------------
# ControlMatrix
# ---------------------------------------------------------------------------


class TestControlMatrix(unittest.TestCase):
    def test_default_has_controls(self):
        matrix = ControlMatrix.default()
        self.assertGreater(len(matrix.controls), 10)

    def test_all_controls_have_ids(self):
        for ctrl in ControlMatrix.default().controls:
            self.assertTrue(ctrl.control_id.startswith("CTL-"))

    def test_get_by_status_implemented(self):
        matrix = ControlMatrix.default()
        implemented = matrix.get_by_status("implemented")
        self.assertGreater(len(implemented), 0)

    def test_get_by_category(self):
        matrix = ControlMatrix.default()
        audit_ctrls = matrix.get_by_category("auditability")
        self.assertGreater(len(audit_ctrls), 0)

    def test_coverage_summary_keys(self):
        summary = ControlMatrix.default().coverage_summary()
        for key in ("total", "implemented", "coverage_pct", "by_category", "by_status"):
            self.assertIn(key, summary)

    def test_coverage_pct_100_when_all_implemented(self):
        matrix = ControlMatrix(
            controls=[
                Control("CTL-T1", "R1", "cat", "desc", "impl", "ev", "implemented"),
                Control("CTL-T2", "R2", "cat", "desc", "impl", "ev", "implemented"),
            ]
        )
        self.assertEqual(matrix.coverage_summary()["coverage_pct"], 100.0)

    def test_coverage_pct_50_with_partial(self):
        matrix = ControlMatrix(
            controls=[
                Control("CTL-T1", "R1", "cat", "desc", "impl", "ev", "implemented"),
                Control("CTL-T2", "R2", "cat", "desc", "impl", "ev", "planned"),
            ]
        )
        self.assertEqual(matrix.coverage_summary()["coverage_pct"], 50.0)

    def test_to_dict_contains_coverage_summary(self):
        d = ControlMatrix.default().to_dict()
        self.assertIn("coverage_summary", d)
        self.assertIn("controls", d)


# ---------------------------------------------------------------------------
# AuditEvent
# ---------------------------------------------------------------------------


class TestAuditEvent(unittest.TestCase):
    def test_create_generates_event_id(self):
        ev = AuditEvent.create(AuditEventType.ANALYSIS_COMPLETED)
        self.assertTrue(len(ev.event_id) > 10)

    def test_create_sets_timestamp(self):
        ev = AuditEvent.create(AuditEventType.ANALYSIS_COMPLETED)
        self.assertIn("T", ev.timestamp)  # ISO format

    def test_create_with_all_fields(self):
        ev = AuditEvent.create(
            AuditEventType.ESCALATION_TRIGGERED,
            filing_id="SEC-001",
            trace_id="trace-001",
            payload={"reason": "critical severity"},
            severity=AuditSeverity.HIGH,
        )
        self.assertEqual(ev.event_type, "ESCALATION_TRIGGERED")
        self.assertEqual(ev.filing_id, "SEC-001")
        self.assertEqual(ev.severity, "HIGH")
        self.assertEqual(ev.payload["reason"], "critical severity")

    def test_to_dict(self):
        d = AuditEvent.create(AuditEventType.FILING_INGESTED, filing_id="X").to_dict()
        self.assertIn("event_id", d)
        self.assertIn("event_type", d)
        self.assertIn("timestamp", d)

    def test_severity_for_event_critical(self):
        self.assertEqual(
            severity_for_event(AuditEventType.ESCALATION_TRIGGERED), AuditSeverity.HIGH
        )

    def test_severity_for_event_warning(self):
        self.assertEqual(
            severity_for_event(AuditEventType.ANALYSIS_FAILED), AuditSeverity.WARNING
        )

    def test_severity_for_event_info(self):
        self.assertEqual(
            severity_for_event(AuditEventType.ANALYSIS_COMPLETED), AuditSeverity.INFO
        )


# ---------------------------------------------------------------------------
# Failure taxonomy
# ---------------------------------------------------------------------------


class TestFailureTaxonomy(unittest.TestCase):
    EXPECTED_CODES = [
        "LLM_UNAVAILABLE",
        "LLM_REFUSED",
        "LLM_MALFORMED_OUTPUT",
        "INGESTION_FAILURE",
        "PARSING_ERROR",
        "CALIBRATION_DRIFT",
        "EXTRACTION_DRIFT",
        "SCHEMA_VIOLATION",
        "ESCALATION_REQUIRED",
        "MEMORY_ERROR",
    ]

    def test_all_expected_codes_present(self):
        for code in self.EXPECTED_CODES:
            self.assertIn(code, FAILURE_TAXONOMY, f"Missing code: {code}")

    def test_all_categories_have_required_fields(self):
        for code, cat in FAILURE_TAXONOMY.items():
            self.assertTrue(cat.code, f"{code}: code is empty")
            self.assertTrue(cat.name, f"{code}: name is empty")
            self.assertTrue(cat.description, f"{code}: description is empty")
            self.assertTrue(cat.remediation, f"{code}: remediation is empty")
            self.assertIn(
                cat.severity,
                ("LOW", "MEDIUM", "HIGH", "CRITICAL"),
                f"{code}: invalid severity {cat.severity}",
            )

    def test_classify_known_code(self):
        cat = classify_failure("LLM_UNAVAILABLE")
        self.assertIsNotNone(cat)
        self.assertEqual(cat.code, "LLM_UNAVAILABLE")

    def test_classify_unknown_code_returns_none(self):
        self.assertIsNone(classify_failure("DOES_NOT_EXIST"))

    def test_auto_escalate_codes_subset_of_taxonomy(self):
        codes = auto_escalate_codes()
        self.assertGreater(len(codes), 0)
        for code in codes:
            self.assertIn(code, FAILURE_TAXONOMY)
            self.assertTrue(FAILURE_TAXONOMY[code].auto_escalate)

    def test_memory_error_is_critical_and_auto_escalates(self):
        cat = FAILURE_TAXONOMY["MEMORY_ERROR"]
        self.assertEqual(cat.severity, "CRITICAL")
        self.assertTrue(cat.auto_escalate)


class TestFailureRecord(unittest.TestCase):
    def test_create_generates_id_and_timestamp(self):
        rec = FailureRecord.create("LLM_UNAVAILABLE")
        self.assertTrue(len(rec.failure_id) > 10)
        self.assertIn("T", rec.timestamp)

    def test_create_with_filing_and_context(self):
        rec = FailureRecord.create(
            "INGESTION_FAILURE",
            filing_id="SEC-001",
            context={"source": "federal_register"},
        )
        self.assertEqual(rec.filing_id, "SEC-001")
        self.assertEqual(rec.context["source"], "federal_register")

    def test_to_dict(self):
        d = FailureRecord.create("PARSING_ERROR").to_dict()
        self.assertIn("failure_id", d)
        self.assertIn("failure_code", d)
        self.assertIn("timestamp", d)


# ---------------------------------------------------------------------------
# EscalationPolicy
# ---------------------------------------------------------------------------


class TestEscalationPolicy(unittest.TestCase):
    def _policy(self):
        return EscalationPolicy.default()

    def test_no_triggers_on_normal_assessment(self):
        reasons = self._policy().evaluate({"severity": "medium", "confidence": 0.85})
        self.assertEqual(reasons, [])

    def test_critical_severity_triggers(self):
        reasons = self._policy().evaluate({"severity": "critical", "confidence": 0.85})
        self.assertTrue(any("CRITICAL" in r for r in reasons))

    def test_low_confidence_triggers(self):
        reasons = self._policy().evaluate({"severity": "low", "confidence": 0.30})
        self.assertTrue(any("Confidence" in r or "confidence" in r for r in reasons))

    def test_calibration_ece_triggers(self):
        reasons = self._policy().evaluate(
            {"severity": "low", "confidence": 0.80},
            calibration_ece=0.20,
        )
        self.assertTrue(
            any(
                "ECE" in r or "Calibration" in r or "calibration" in r.lower()
                for r in reasons
            )
        )

    def test_drift_triggers(self):
        reasons = self._policy().evaluate(
            {"severity": "low", "confidence": 0.80},
            drift_detected=True,
        )
        self.assertTrue(any("drift" in r.lower() for r in reasons))

    def test_multiple_triggers_all_reported(self):
        reasons = self._policy().evaluate(
            {"severity": "critical", "confidence": 0.25},
            calibration_ece=0.20,
            drift_detected=True,
        )
        self.assertGreaterEqual(len(reasons), 3)

    def test_from_dict(self):
        data = {
            "name": "custom",
            "block_alert_on_escalation": False,
            "triggers": [
                {
                    "condition_id": "test_trigger",
                    "description": "Test",
                    "field": "confidence",
                    "operator": "lte",
                    "threshold": 0.5,
                    "reason_template": "Confidence {value} too low",
                }
            ],
        }
        policy = EscalationPolicy.from_dict(data)
        reasons = policy.evaluate({"confidence": 0.30})
        self.assertEqual(len(reasons), 1)

    def test_to_dict_roundtrip(self):
        policy = EscalationPolicy.default()
        d = policy.to_dict()
        policy2 = EscalationPolicy.from_dict(d)
        self.assertEqual(len(policy.triggers), len(policy2.triggers))


# ---------------------------------------------------------------------------
# FallbackPolicy
# ---------------------------------------------------------------------------


class TestFallbackPolicy(unittest.TestCase):
    def _policy(self):
        return FallbackPolicy.default()

    def test_default_has_rules_for_all_failure_codes(self):
        policy = self._policy()
        for code in FAILURE_TAXONOMY:
            action = policy.select(code)
            self.assertIn("action", action)
            self.assertIn("label", action)

    def test_llm_unavailable_uses_cached(self):
        action = self._policy().select("LLM_UNAVAILABLE", {"cached_age_hours": 2})
        self.assertEqual(action["action"], "use_cached")

    def test_llm_unavailable_falls_to_human_when_cache_stale(self):
        action = self._policy().select("LLM_UNAVAILABLE", {"cached_age_hours": 48})
        self.assertEqual(action["action"], "require_human")

    def test_unknown_code_requires_human(self):
        action = self._policy().select("UNKNOWN_CODE")
        self.assertEqual(action["action"], "require_human")

    def test_all_actions_have_labels(self):
        for code in FAILURE_TAXONOMY:
            action = self._policy().select(code)
            self.assertIn(action["action"], FALLBACK_ACTIONS)

    def test_from_dict(self):
        data = {
            "name": "custom",
            "cache_max_age_hours": 12,
            "min_confidence_for_alert": 0.5,
            "rules": {"LLM_UNAVAILABLE": "use_stub"},
        }
        policy = FallbackPolicy.from_dict(data)
        action = policy.select("LLM_UNAVAILABLE")
        self.assertEqual(action["action"], "use_stub")

    def test_to_dict_roundtrip(self):
        policy = FallbackPolicy.default()
        d = policy.to_dict()
        policy2 = FallbackPolicy.from_dict(d)
        self.assertEqual(policy.rules, policy2.rules)


# ---------------------------------------------------------------------------
# MemoryStore audit_log CRUD
# ---------------------------------------------------------------------------


class TestMemoryStoreAuditLog(unittest.TestCase):
    def setUp(self):
        self.mem = make_mem()

    def tearDown(self):
        self.mem.close()

    def _make_event(
        self,
        event_type=AuditEventType.ANALYSIS_COMPLETED,
        filing_id=None,
        severity=AuditSeverity.INFO,
    ):
        return AuditEvent.create(
            event_type, filing_id=filing_id, payload={"test": True}, severity=severity
        )

    def test_emit_and_retrieve(self):
        ev = self._make_event(filing_id="SEC-001")
        self.mem.emit_audit_event(ev)
        events = self.mem.get_audit_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["filing_id"], "SEC-001")

    def test_filter_by_event_type(self):
        self.mem.emit_audit_event(self._make_event(AuditEventType.ANALYSIS_COMPLETED))
        self.mem.emit_audit_event(self._make_event(AuditEventType.ESCALATION_TRIGGERED))
        escalations = self.mem.get_audit_events(event_type="ESCALATION_TRIGGERED")
        self.assertEqual(len(escalations), 1)

    def test_filter_by_filing_id(self):
        self.mem.emit_audit_event(self._make_event(filing_id="F-001"))
        self.mem.emit_audit_event(self._make_event(filing_id="F-002"))
        results = self.mem.get_audit_events(filing_id="F-001")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["filing_id"], "F-001")

    def test_filter_by_severity(self):
        self.mem.emit_audit_event(self._make_event(severity=AuditSeverity.INFO))
        self.mem.emit_audit_event(self._make_event(severity=AuditSeverity.HIGH))
        highs = self.mem.get_audit_events(severity="HIGH")
        self.assertEqual(len(highs), 1)

    def test_payload_is_deserialised(self):
        ev = AuditEvent.create(
            AuditEventType.ANALYSIS_COMPLETED, payload={"key": "value", "num": 42}
        )
        self.mem.emit_audit_event(ev)
        events = self.mem.get_audit_events()
        self.assertEqual(events[0]["payload"]["key"], "value")
        self.assertEqual(events[0]["payload"]["num"], 42)

    def test_duplicate_event_id_ignored(self):
        ev = self._make_event()
        self.mem.emit_audit_event(ev)
        self.mem.emit_audit_event(ev)  # Second emit — should be ignored
        self.assertEqual(len(self.mem.get_audit_events()), 1)

    def test_limit_respected(self):
        for _i in range(10):
            self.mem.emit_audit_event(
                AuditEvent.create(AuditEventType.ANALYSIS_COMPLETED)
            )
        results = self.mem.get_audit_events(limit=3)
        self.assertEqual(len(results), 3)


if __name__ == "__main__":
    unittest.main()
