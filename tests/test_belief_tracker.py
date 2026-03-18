"""Tests for Priority 3: prior/posterior belief tracking.

Covers:
- MemoryStore belief state CRUD (store, retrieve, history)
- BeliefTrackerSkill: first observation, sequential updates, delta math,
  stability and reversal risk, parameter clamping, and memory-denied path.
- BeliefState dataclass fields on MonitorResult.
"""

import math
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from naturalsentinel.memory.store import MemoryStore
from naturalsentinel.models import BeliefState, MonitorResult
from naturalsentinel.skills.belief_tracker import (
    BeliefTrackerSkill,
    _compute_delta_drivers,
    _compute_stability_score,
    _compute_reversal_risk,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mem():
    store = MemoryStore(":memory:")
    return store


class FakeContext:
    def __init__(self, memory, params):
        self.memory = memory
        self.params = params


def _make_context(mem_store, params: dict):
    return FakeContext(mem_store, params)


def approx_eq(a, b, tol=1e-4):
    return abs(a - b) < tol


# ---------------------------------------------------------------------------
# MemoryStore belief CRUD
# ---------------------------------------------------------------------------

class TestMemoryStoreBeliefCRUD(unittest.TestCase):
    def setUp(self):
        self.mem = make_mem()

    def tearDown(self):
        self.mem.close()

    def test_get_nonexistent_returns_none(self):
        result = self.mem.get_belief_state("unknown_topic", "sec")
        self.assertIsNone(result)

    def test_store_and_retrieve(self):
        belief = {
            "prior_confidence": 0.5,
            "posterior_confidence": 0.65,
            "delta_confidence": 0.15,
            "delta_drivers": ["Positive signal from new filing"],
            "stability_score": 0.9,
            "reversal_risk": 0.2,
            "observation_count": 1,
            "last_filing_id": "SEC-2026-001",
        }
        self.mem.store_belief_state("climate_esg", "sec", belief)
        retrieved = self.mem.get_belief_state("climate_esg", "sec")
        self.assertIsNotNone(retrieved)
        self.assertTrue(approx_eq(retrieved["posterior_confidence"], 0.65))
        self.assertTrue(approx_eq(retrieved["delta_confidence"], 0.15))
        self.assertIn("Positive signal from new filing", retrieved["delta_drivers"])

    def test_upsert_updates_posterior(self):
        b1 = {
            "prior_confidence": 0.5, "posterior_confidence": 0.60,
            "delta_confidence": 0.10, "delta_drivers": ["First update"],
            "stability_score": 1.0, "reversal_risk": 0.1,
            "observation_count": 1, "last_filing_id": "F-001",
        }
        self.mem.store_belief_state("topic_a", "fed", b1)

        b2 = {**b1, "posterior_confidence": 0.75, "delta_confidence": 0.15,
              "delta_drivers": ["Second update"], "observation_count": 2,
              "last_filing_id": "F-002"}
        self.mem.store_belief_state("topic_a", "fed", b2)

        retrieved = self.mem.get_belief_state("topic_a", "fed")
        self.assertTrue(approx_eq(retrieved["posterior_confidence"], 0.75))
        self.assertEqual(retrieved["observation_count"], 2)

    def test_history_accumulates(self):
        for i in range(3):
            self.mem.store_belief_state("topic_b", "cfpb", {
                "prior_confidence": 0.5,
                "posterior_confidence": 0.5 + i * 0.1,
                "delta_confidence": 0.1,
                "delta_drivers": [f"Update {i}"],
                "stability_score": 0.9, "reversal_risk": 0.1,
                "observation_count": i + 1, "last_filing_id": f"F-{i}",
            })
        history = self.mem.get_belief_history("topic_b", "cfpb")
        self.assertEqual(len(history), 3)

    def test_list_belief_states_all(self):
        base = {"prior_confidence": 0.5, "posterior_confidence": 0.6,
                "delta_confidence": 0.1, "delta_drivers": [], "stability_score": 1.0,
                "reversal_risk": 0.1, "observation_count": 1, "last_filing_id": ""}
        self.mem.store_belief_state("t1", "sec", base)
        self.mem.store_belief_state("t2", "fed", base)
        all_states = self.mem.list_belief_states()
        self.assertEqual(len(all_states), 2)

    def test_list_belief_states_filtered(self):
        base = {"prior_confidence": 0.5, "posterior_confidence": 0.6,
                "delta_confidence": 0.1, "delta_drivers": [], "stability_score": 1.0,
                "reversal_risk": 0.1, "observation_count": 1, "last_filing_id": ""}
        self.mem.store_belief_state("t1", "sec", base)
        self.mem.store_belief_state("t2", "fed", base)
        sec_states = self.mem.list_belief_states(domain="sec")
        self.assertEqual(len(sec_states), 1)
        self.assertEqual(sec_states[0]["topic"], "t1")


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------

class TestComputeDeltaDrivers(unittest.TestCase):
    def test_minimal_shift(self):
        drivers = _compute_delta_drivers(0.5, 0.51, 0.01, "F-001", "", "")
        self.assertTrue(any("Minimal" in d for d in drivers))

    def test_strong_positive(self):
        drivers = _compute_delta_drivers(0.4, 0.65, 0.25, "F-001", "", "final_rule")
        self.assertTrue(any("Strong positive" in d for d in drivers))
        self.assertTrue(any("final_rule" in d or "narrows" in d for d in drivers))

    def test_strong_negative(self):
        drivers = _compute_delta_drivers(0.7, 0.45, -0.25, "F-002", "", "proposed_rule")
        self.assertTrue(any("Strong negative" in d for d in drivers))
        self.assertTrue(any("proposed" in d.lower() for d in drivers))

    def test_evidence_summary_included(self):
        drivers = _compute_delta_drivers(0.5, 0.6, 0.1, "F-001", "Capital buffer raised 2%", "")
        self.assertTrue(any("Capital buffer" in d for d in drivers))

    def test_filing_id_included(self):
        drivers = _compute_delta_drivers(0.5, 0.6, 0.1, "MY-FILING-99", "", "")
        self.assertTrue(any("MY-FILING-99" in d for d in drivers))

    def test_low_prior_upgrade_noted(self):
        drivers = _compute_delta_drivers(0.2, 0.45, 0.25, "F-003", "", "guidance")
        self.assertTrue(any("low-confidence" in d or "weak" in d.lower() for d in drivers))


class TestComputeStabilityScore(unittest.TestCase):
    def test_empty_history_returns_one(self):
        self.assertEqual(_compute_stability_score([]), 1.0)

    def test_single_entry_returns_one(self):
        self.assertEqual(_compute_stability_score([{"delta_confidence": 0.1}]), 1.0)

    def test_perfectly_stable_returns_one(self):
        history = [{"delta_confidence": 0.1}] * 5
        score = _compute_stability_score(history)
        self.assertTrue(approx_eq(score, 1.0))

    def test_volatile_returns_low(self):
        history = [{"delta_confidence": 0.5 if i % 2 == 0 else -0.5} for i in range(6)]
        score = _compute_stability_score(history)
        self.assertLess(score, 0.5)

    def test_bounded_between_zero_and_one(self):
        history = [{"delta_confidence": (-1.0 if i % 2 == 0 else 1.0)} for i in range(8)]
        score = _compute_stability_score(history)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestComputeReversalRisk(unittest.TestCase):
    def test_stable_low_risk(self):
        history = [{"delta_confidence": 0.05}] * 5
        risk = _compute_reversal_risk(0.05, 0.7, history)
        self.assertLess(risk, 0.4)

    def test_oscillation_raises_risk(self):
        history = [
            {"delta_confidence": 0.3},
            {"delta_confidence": -0.3},
            {"delta_confidence": 0.3},
        ]
        risk = _compute_reversal_risk(0.3, 0.6, history)
        self.assertGreater(risk, 0.4)

    def test_large_delta_raises_risk(self):
        risk_large = _compute_reversal_risk(0.5, 0.7, [])
        risk_small = _compute_reversal_risk(0.05, 0.7, [])
        self.assertGreater(risk_large, risk_small)

    def test_low_posterior_raises_risk(self):
        risk_low = _compute_reversal_risk(0.1, 0.2, [])
        risk_high = _compute_reversal_risk(0.1, 0.9, [])
        self.assertGreater(risk_low, risk_high)

    def test_bounded_between_zero_and_one(self):
        risk = _compute_reversal_risk(1.0, 0.0, [{"delta_confidence": 1.0}] * 5)
        self.assertGreaterEqual(risk, 0.0)
        self.assertLessEqual(risk, 1.0)


# ---------------------------------------------------------------------------
# BeliefTrackerSkill integration tests
# ---------------------------------------------------------------------------

class TestBeliefTrackerSkill(unittest.TestCase):
    def setUp(self):
        self.mem = make_mem()
        self.skill = BeliefTrackerSkill()

    def tearDown(self):
        self.mem.close()

    def _ctx(self, **params):
        return _make_context(self.mem, params)

    def test_first_observation_seeds_from_neutral_prior(self):
        result = self.skill.execute(self._ctx(
            topic="prudential_capital_tightening",
            domain="fed",
            new_confidence=0.70,
            filing_id="FED-2026-001",
            evidence_summary="Basel IV output floor finalised",
            change_type="final_rule",
            learning_rate=0.40,
        ))
        self.assertTrue(result.success)
        data = result.data
        self.assertTrue(approx_eq(data["prior_confidence"], 0.50))
        self.assertGreater(data["posterior_confidence"], 0.50)
        self.assertLess(data["posterior_confidence"], 0.70)
        self.assertGreater(data["delta_confidence"], 0)
        self.assertEqual(data["observation_count"], 1)
        self.assertEqual(data["last_filing_id"], "FED-2026-001")

    def test_second_observation_uses_stored_prior(self):
        result1 = self.skill.execute(self._ctx(
            topic="climate_esg_integration", domain="sec",
            new_confidence=0.60, filing_id="SEC-001", learning_rate=0.40,
        ))
        posterior_1 = result1.data["posterior_confidence"]

        result2 = self.skill.execute(self._ctx(
            topic="climate_esg_integration", domain="sec",
            new_confidence=0.80, filing_id="SEC-002", learning_rate=0.40,
        ))
        self.assertTrue(approx_eq(result2.data["prior_confidence"], posterior_1))
        self.assertEqual(result2.data["observation_count"], 2)

    def test_negative_delta_on_drop(self):
        self.skill.execute(self._ctx(
            topic="digital_asset_capture", domain="sec",
            new_confidence=0.80, learning_rate=0.95,
        ))
        result = self.skill.execute(self._ctx(
            topic="digital_asset_capture", domain="sec",
            new_confidence=0.10, learning_rate=0.60,
        ))
        self.assertLess(result.data["delta_confidence"], 0)

    def test_stability_high_for_stable_observations(self):
        for val in [0.60, 0.61, 0.62, 0.60, 0.61]:
            self.skill.execute(self._ctx(
                topic="liquidity_stress", domain="fed", new_confidence=val,
            ))
        final = self.skill.execute(self._ctx(
            topic="liquidity_stress", domain="fed", new_confidence=0.61,
        ))
        self.assertGreater(final.data["stability_score"], 0.7)

    def test_reversal_risk_bounded(self):
        result = self.skill.execute(self._ctx(
            topic="frtb_market_risk", domain="basel", new_confidence=0.95,
        ))
        rr = result.data["reversal_risk"]
        self.assertGreaterEqual(rr, 0.0)
        self.assertLessEqual(rr, 1.0)

    def test_delta_drivers_populated(self):
        result = self.skill.execute(self._ctx(
            topic="consumer_protection", domain="cfpb",
            new_confidence=0.75,
            evidence_summary="UDAAP guidance expanded",
            change_type="guidance",
        ))
        drivers = result.data["delta_drivers"]
        self.assertIsInstance(drivers, list)
        self.assertGreater(len(drivers), 0)
        self.assertTrue(any("UDAAP" in d for d in drivers))

    def test_confidence_clamped_at_one(self):
        result = self.skill.execute(self._ctx(
            topic="test_clamp", domain="sec", new_confidence=1.5,
        ))
        self.assertLessEqual(result.data["posterior_confidence"], 1.0)

    def test_confidence_clamped_at_zero(self):
        result = self.skill.execute(self._ctx(
            topic="test_clamp_low", domain="sec", new_confidence=-0.5,
        ))
        self.assertGreaterEqual(result.data["posterior_confidence"], 0.0)

    def test_memory_denied_returns_failure(self):
        ctx = _make_context(None, {"topic": "any", "domain": "sec", "new_confidence": 0.5})
        result = self.skill.execute(ctx)
        self.assertFalse(result.success)
        self.assertIn("denied", result.error.lower())

    def test_persists_to_memory(self):
        self.skill.execute(self._ctx(
            topic="resolution_tlac", domain="fdic",
            new_confidence=0.55, filing_id="FDIC-2026-009",
        ))
        stored = self.mem.get_belief_state("resolution_tlac", "fdic")
        self.assertIsNotNone(stored)
        self.assertEqual(stored["last_filing_id"], "FDIC-2026-009")

    def test_history_recorded_in_memory(self):
        for _ in range(3):
            self.skill.execute(self._ctx(
                topic="derivatives_margin", domain="cftc", new_confidence=0.65,
            ))
        history = self.mem.get_belief_history("derivatives_margin", "cftc")
        self.assertEqual(len(history), 3)

    def test_metadata_in_result(self):
        result = self.skill.execute(self._ctx(
            topic="model_risk", domain="occ", new_confidence=0.72,
        ))
        self.assertEqual(result.metadata["topic"], "model_risk")
        self.assertEqual(result.metadata["domain"], "occ")
        self.assertIn("delta_confidence", result.metadata)
        self.assertIn("stability_score", result.metadata)
        self.assertIn("reversal_risk", result.metadata)


# ---------------------------------------------------------------------------
# BeliefState dataclass and MonitorResult integration
# ---------------------------------------------------------------------------

class TestBeliefStateModel(unittest.TestCase):
    def test_belief_state_fields(self):
        from datetime import datetime
        bs = BeliefState(
            topic="prudential_capital_tightening",
            domain="fed",
            prior_confidence=0.50,
            posterior_confidence=0.65,
            delta_confidence=0.15,
            delta_drivers=["New evidence"],
            stability_score=0.85,
            reversal_risk=0.20,
            observation_count=3,
            last_filing_id="FED-2026-001",
        )
        self.assertEqual(bs.topic, "prudential_capital_tightening")
        self.assertTrue(approx_eq(bs.delta_confidence, 0.15))
        self.assertEqual(bs.observation_count, 3)
        datetime.fromisoformat(bs.updated_at)

    def test_monitor_result_includes_belief_states(self):
        from naturalsentinel.models import (
            RegulatoryFiling, ImpactAssessment, DecisionFrame,
            RegulatoryDomain, Severity,
        )
        filing = RegulatoryFiling(
            id="SEC-001", title="Test", domain=RegulatoryDomain.SEC,
            source_url="http://example.com", published_date="2026-01-01",
            raw_text="text",
        )
        impact = ImpactAssessment(
            filing_id="SEC-001", severity=Severity.MEDIUM,
            affected_business_lines=[], affected_regulations=[],
            compliance_deadline=None, action_items=[],
            risk_summary="ok", confidence=0.7,
        )
        decision = DecisionFrame(
            decision_id="D-001", question="q", scope="s", time_horizon="1y"
        )
        bs = BeliefState(
            topic="climate_esg", domain="sec",
            prior_confidence=0.4, posterior_confidence=0.55,
            delta_confidence=0.15, delta_drivers=[], stability_score=0.9,
            reversal_risk=0.15, observation_count=1,
        )
        result = MonitorResult(filing=filing, impact=impact, decision=decision,
                               belief_states=[bs])
        self.assertEqual(len(result.belief_states), 1)
        self.assertEqual(result.belief_states[0].topic, "climate_esg")


if __name__ == "__main__":
    unittest.main()
