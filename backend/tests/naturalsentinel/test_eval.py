"""Tests for the quantitative evaluation layer.

Covers:
- scorer: FieldScore, CaseScore, SuiteScore for each field type
- calibration: CalibrationReport ECE/MCE computation
- drift: DriftReport TV distance and effect-size detection
- benchmark: BenchmarkCase/BenchmarkSuite construction from feedback_log
- MemoryStore eval_run CRUD and comparison
- RunEvaluationSkill: historical mode, fixture mode, empty-feedback path,
  memory-denied path, report persistence
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.naturalsentinel.eval.benchmark import (
    BenchmarkCase,
    BenchmarkSuite,
    load_suite_from_feedback,
    load_suite_from_fixture,
)
from app.naturalsentinel.eval.calibration import build_calibration_report
from app.naturalsentinel.eval.drift import (
    _categorical_distribution,
    _effect_size,
    _tv_distance,
    build_drift_report,
)
from app.naturalsentinel.eval.scorer import (
    CaseScore,
    score_case,
    score_field,
    score_suite,
)
from app.naturalsentinel.memory.store import MemoryStore
from app.naturalsentinel.skills.run_evaluation import RunEvaluationSkill

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


def make_case(
    case_id="c-001",
    predicted=None,
    expected=None,
    labeled_fields=None,
    domain="sec",
):
    predicted = predicted or {
        "severity": "high",
        "change_type": "final_rule",
        "affected_business_lines": ["Equities", "Fixed Income"],
        "affected_regulations": ["Reg S-K", "Reg S-X"],
        "compliance_deadline": "2026-06-30",
        "action_items": ["Update model", "File report"],
        "confidence": 0.80,
    }
    expected = expected or {
        "severity": "high",
        "change_type": "final_rule",
        "affected_business_lines": ["Equities", "Fixed Income"],
        "affected_regulations": ["Reg S-K", "Reg S-X"],
        "compliance_deadline": "2026-06-30",
    }
    labeled_fields = list(expected.keys()) if labeled_fields is None else labeled_fields
    return BenchmarkCase(
        case_id=case_id,
        filing={"domain": domain, "id": case_id},
        predicted=predicted,
        expected=expected,
        labeled_fields=labeled_fields,
    )


def approx_eq(a, b, tol=1e-4):
    return abs(a - b) < tol


# ---------------------------------------------------------------------------
# scorer — FieldScore
# ---------------------------------------------------------------------------


class TestScoreField(unittest.TestCase):
    # --- Categorical ---
    def test_exact_match_categorical(self):
        fs = score_field("severity", "high", "high")
        self.assertEqual(fs.score, 1.0)
        self.assertEqual(fs.metric, "exact_match")

    def test_case_insensitive_categorical(self):
        fs = score_field("severity", "HIGH", "high")
        self.assertEqual(fs.score, 1.0)

    def test_mismatch_categorical(self):
        fs = score_field("severity", "low", "critical")
        self.assertEqual(fs.score, 0.0)

    def test_change_type_match(self):
        fs = score_field("change_type", "final_rule", "final_rule")
        self.assertEqual(fs.score, 1.0)

    # --- Set fields ---
    def test_jaccard_perfect(self):
        fs = score_field("affected_business_lines", ["A", "B"], ["A", "B"])
        self.assertEqual(fs.score, 1.0)
        self.assertEqual(fs.metric, "jaccard")

    def test_jaccard_partial(self):
        fs = score_field("affected_business_lines", ["A", "B", "C"], ["A", "B"])
        # intersection=2, union=3 → 2/3
        self.assertTrue(approx_eq(fs.score, 2 / 3))

    def test_jaccard_no_overlap(self):
        fs = score_field("affected_regulations", ["X"], ["Y"])
        self.assertEqual(fs.score, 0.0)

    def test_jaccard_both_empty(self):
        fs = score_field("affected_business_lines", [], [])
        self.assertEqual(fs.score, 1.0)

    def test_jaccard_one_empty(self):
        fs = score_field("affected_business_lines", [], ["A"])
        self.assertEqual(fs.score, 0.0)

    # --- Date field ---
    def test_date_both_null(self):
        fs = score_field("compliance_deadline", None, None)
        self.assertEqual(fs.score, 1.0)
        self.assertEqual(fs.metric, "date_match")

    def test_date_exact_match(self):
        fs = score_field("compliance_deadline", "2026-06-30", "2026-06-30")
        self.assertEqual(fs.score, 1.0)

    def test_date_mismatch(self):
        fs = score_field("compliance_deadline", "2026-06-30", "2026-12-31")
        self.assertEqual(fs.score, 0.0)

    def test_date_one_null(self):
        fs = score_field("compliance_deadline", None, "2026-06-30")
        self.assertEqual(fs.score, 0.0)

    # --- Count field ---
    def test_count_ratio_equal(self):
        fs = score_field("action_items", ["a", "b", "c"], ["x", "y", "z"])
        self.assertEqual(fs.score, 1.0)
        self.assertEqual(fs.metric, "count_ratio")

    def test_count_ratio_partial(self):
        fs = score_field("action_items", ["a"], ["x", "y", "z"])
        self.assertTrue(approx_eq(fs.score, 1 / 3))

    def test_count_both_zero(self):
        fs = score_field("action_items", [], [])
        self.assertEqual(fs.score, 1.0)

    # --- Unknown field ---
    def test_unknown_field_neutral(self):
        fs = score_field("unknown_field_xyz", "foo", "bar")
        self.assertEqual(fs.score, 0.5)
        self.assertEqual(fs.metric, "unknown")


# ---------------------------------------------------------------------------
# scorer — CaseScore and SuiteScore
# ---------------------------------------------------------------------------


class TestScoreCase(unittest.TestCase):
    def test_perfect_case(self):
        case = make_case()
        cs = score_case(case)
        self.assertTrue(approx_eq(cs.overall_score, 1.0))
        self.assertEqual(cs.case_id, "c-001")

    def test_mixed_case(self):
        case = make_case(
            predicted={
                "severity": "low",  # Wrong
                "change_type": "final_rule",  # Correct
                "confidence": 0.6,
            },
            expected={"severity": "high", "change_type": "final_rule"},
            labeled_fields=["severity", "change_type"],
        )
        cs = score_case(case)
        # severity=0.0, change_type=1.0 → 0.5
        self.assertTrue(approx_eq(cs.overall_score, 0.5))

    def test_empty_labeled_fields(self):
        case = make_case(labeled_fields=[])
        cs = score_case(case)
        self.assertEqual(cs.overall_score, 0.0)

    def test_confidence_captured(self):
        case = make_case(predicted={**make_case().predicted, "confidence": 0.77})
        cs = score_case(case)
        self.assertTrue(approx_eq(cs.confidence, 0.77))

    def test_domain_captured(self):
        case = make_case(domain="cfpb")
        cs = score_case(case)
        self.assertEqual(cs.domain, "cfpb")


class TestScoreSuite(unittest.TestCase):
    def test_single_perfect_case(self):
        suite = BenchmarkSuite("test", cases=[make_case()])
        ss = score_suite(suite)
        self.assertEqual(ss.n_cases, 1)
        self.assertTrue(approx_eq(ss.overall_accuracy, 1.0))

    def test_aggregation(self):
        # Case 1: severity correct (1.0); Case 2: severity wrong (0.0)
        c1 = make_case(
            "c1",
            predicted={"severity": "high", "confidence": 0.8},
            expected={"severity": "high"},
            labeled_fields=["severity"],
        )
        c2 = make_case(
            "c2",
            predicted={"severity": "low", "confidence": 0.9},
            expected={"severity": "critical"},
            labeled_fields=["severity"],
        )
        suite = BenchmarkSuite("t", cases=[c1, c2])
        ss = score_suite(suite)
        self.assertTrue(approx_eq(ss.per_field_accuracy["severity"], 0.5))
        self.assertTrue(approx_eq(ss.overall_accuracy, 0.5))

    def test_per_field_count(self):
        suite = BenchmarkSuite(
            "t",
            cases=[
                make_case("c1", labeled_fields=["severity"]),
                make_case("c2", labeled_fields=["severity", "change_type"]),
            ],
        )
        ss = score_suite(suite)
        self.assertEqual(ss.n_fields_evaluated["severity"], 2)
        self.assertEqual(ss.n_fields_evaluated["change_type"], 1)

    def test_domain_breakdown(self):
        c1 = make_case("c1", domain="sec")
        c2 = make_case("c2", domain="fed")
        suite = BenchmarkSuite("t", cases=[c1, c2])
        ss = score_suite(suite)
        self.assertIn("sec", ss.domain_breakdown)
        self.assertIn("fed", ss.domain_breakdown)

    def test_empty_suite(self):
        ss = score_suite(BenchmarkSuite("empty"))
        self.assertEqual(ss.n_cases, 0)
        self.assertEqual(ss.overall_accuracy, 0.0)


# ---------------------------------------------------------------------------
# calibration
# ---------------------------------------------------------------------------


class TestCalibration(unittest.TestCase):
    def _make_case_score(self, confidence, overall_score):
        cs = CaseScore(case_id="x")
        cs.confidence = confidence
        cs.overall_score = overall_score
        return cs

    def test_empty_returns_no_data(self):
        report = build_calibration_report([])
        self.assertIn("No data", report.assessment)

    def test_perfect_calibration(self):
        # All cases in bucket 0.8-0.9, all correct → ECE ≈ |0.85 - 1.0| per bucket
        # Not actually zero ECE (confidence ≠ accuracy) — just verifying structure
        cases = [self._make_case_score(0.85, 0.9) for _ in range(20)]
        report = build_calibration_report(cases)
        self.assertGreater(len(report.buckets), 0)
        self.assertGreaterEqual(report.ece, 0.0)
        self.assertLessEqual(report.ece, 1.0)
        self.assertGreaterEqual(report.mce, 0.0)

    def test_severely_miscalibrated(self):
        # High confidence, all wrong
        cases = [self._make_case_score(0.95, 0.0) for _ in range(10)]
        report = build_calibration_report(cases)
        self.assertGreater(report.ece, 0.5)
        self.assertIn("miscalibrated", report.assessment.lower())

    def test_well_calibrated_ece_low(self):
        # ECE = 0: every bucket has confidence == accuracy
        # Build: 10 cases at conf=0.05, all wrong (accuracy=0) → |0.05-0|=0.05
        # To get truly low ECE we need confidence ~ accuracy
        # Confidence ≈ 0.0, accuracy = 0.0 → ECE ≈ 0.0
        cases = [self._make_case_score(0.01, 0.0) for _ in range(10)]
        report = build_calibration_report(cases)
        self.assertLess(report.ece, 0.10)

    def test_buckets_have_correct_fields(self):
        cases = [self._make_case_score(0.7, 0.8) for _ in range(5)]
        report = build_calibration_report(cases)
        bucket = report.buckets[0]
        self.assertIsNotNone(bucket.lower)
        self.assertIsNotNone(bucket.upper)
        self.assertIsNotNone(bucket.count)
        self.assertIsNotNone(bucket.mean_confidence)
        self.assertIsNotNone(bucket.mean_accuracy)
        self.assertIsNotNone(bucket.calibration_error)

    def test_n_samples_matches_input(self):
        cases = [self._make_case_score(0.5, 0.5) for _ in range(15)]
        report = build_calibration_report(cases)
        self.assertEqual(report.n_samples, 15)


# ---------------------------------------------------------------------------
# drift
# ---------------------------------------------------------------------------


class TestDriftHelpers(unittest.TestCase):
    def test_tv_distance_identical(self):
        d = {"a": 0.5, "b": 0.5}
        self.assertEqual(_tv_distance(d, d), 0.0)

    def test_tv_distance_disjoint(self):
        a = {"x": 1.0}
        b = {"y": 1.0}
        self.assertEqual(_tv_distance(a, b), 1.0)

    def test_categorical_distribution_sums_to_one(self):
        dist = _categorical_distribution(["a", "a", "b"])
        total = sum(dist.values())
        self.assertTrue(approx_eq(total, 1.0))

    def test_effect_size_zero_for_identical(self):
        s = {"mean": 0.5, "std": 0.1}
        self.assertEqual(_effect_size(s, s), 0.0)

    def test_effect_size_large(self):
        a = {"mean": 0.0, "std": 0.1}
        b = {"mean": 2.0, "std": 0.1}
        # d = 2/0.1 = 20 → clamped to 1.0
        self.assertEqual(_effect_size(a, b), 1.0)

    def test_effect_size_zero_std(self):
        a = {"mean": 0.5, "std": 0.0}
        b = {"mean": 0.5, "std": 0.0}
        self.assertEqual(_effect_size(a, b), 0.0)

    def test_effect_size_zero_std_diff_mean(self):
        a = {"mean": 0.3, "std": 0.0}
        b = {"mean": 0.7, "std": 0.0}
        self.assertEqual(_effect_size(a, b), 1.0)


class TestBuildDriftReport(unittest.TestCase):
    def _make_impact(
        self, severity="medium", confidence=0.7, change_type="guidance", lines=None
    ):
        return {
            "severity": severity,
            "confidence": confidence,
            "change_type": change_type,
            "affected_business_lines": lines or ["Equities"],
        }

    def test_identical_windows_no_drift(self):
        window = [self._make_impact() for _ in range(10)]
        report = build_drift_report(window, window)
        self.assertFalse(report.drift_detected)
        self.assertEqual(report.overall_drift_score, 0.0)

    def test_different_severity_detected(self):
        a = [self._make_impact("low") for _ in range(10)]
        b = [self._make_impact("critical") for _ in range(10)]
        report = build_drift_report(a, b, drift_threshold=0.05)
        sev_metric = next(m for m in report.metrics if m.field == "severity")
        self.assertTrue(sev_metric.drift_detected)

    def test_report_contains_all_fields(self):
        a = [self._make_impact() for _ in range(5)]
        b = [
            self._make_impact("high", 0.9, "final_rule", ["Fixed Income"])
            for _ in range(5)
        ]
        report = build_drift_report(a, b)
        field_names = {m.field for m in report.metrics}
        self.assertIn("severity", field_names)
        self.assertIn("confidence", field_names)
        self.assertIn("affected_business_lines", field_names)
        self.assertIn("change_type", field_names)

    def test_empty_windows_gives_empty_metrics(self):
        report = build_drift_report([], [])
        self.assertEqual(len(report.metrics), 0)
        self.assertIn("Insufficient", report.summary)

    def test_summary_mentions_drift_fields(self):
        a = [self._make_impact("low") for _ in range(10)]
        b = [self._make_impact("critical") for _ in range(10)]
        report = build_drift_report(a, b, drift_threshold=0.05)
        if report.drift_detected:
            self.assertIn("severity", report.summary)


# ---------------------------------------------------------------------------
# benchmark — load_suite_from_feedback
# ---------------------------------------------------------------------------


class TestLoadSuiteFromFeedback(unittest.TestCase):
    def setUp(self):
        self.mem = make_mem()
        # Seed episodic memory + feedback
        self.mem.store_episodic(
            "F-001",
            {"id": "F-001", "title": "Test Filing", "domain": "sec", "summary": ""},
            {
                "severity": "medium",
                "confidence": 0.7,
                "affected_business_lines": [],
                "affected_regulations": [],
                "risk_summary": "test",
            },
        )
        self.mem.record_feedback(
            "F-001", "severity", "medium", "high", "under-estimated"
        )

    def tearDown(self):
        self.mem.close()

    def test_loads_case_from_feedback(self):
        suite = load_suite_from_feedback(self.mem)
        self.assertEqual(len(suite.cases), 1)
        case = suite.cases[0]
        self.assertIn("severity", case.labeled_fields)
        self.assertEqual(case.expected["severity"], "high")
        self.assertEqual(case.predicted["severity"], "medium")

    def test_filters_by_domain(self):
        suite = load_suite_from_feedback(self.mem, domains=["fed"])
        self.assertEqual(len(suite.cases), 0)

    def test_empty_feedback_log(self):
        empty_mem = make_mem()
        suite = load_suite_from_feedback(empty_mem)
        self.assertEqual(len(suite.cases), 0)
        empty_mem.close()


class TestLoadSuiteFromFixture(unittest.TestCase):
    def test_loads_json_fixture(self):
        fixture = [
            {
                "case_id": "fix-001",
                "filing": {"domain": "sec", "id": "fix-001"},
                "predicted": {"severity": "medium", "confidence": 0.8},
                "expected": {"severity": "high"},
                "labeled_fields": ["severity"],
                "source": "fixture",
                "tags": ["sec"],
            }
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            json.dump(fixture, fh)
            fh_name = fh.name
        try:
            suite = load_suite_from_fixture(fh_name)
            self.assertEqual(len(suite.cases), 1)
            self.assertEqual(suite.cases[0].case_id, "fix-001")
            self.assertEqual(suite.cases[0].expected["severity"], "high")
        finally:
            os.unlink(fh_name)


# ---------------------------------------------------------------------------
# MemoryStore eval_run CRUD
# ---------------------------------------------------------------------------


class TestMemoryStoreEvalCRUD(unittest.TestCase):
    def setUp(self):
        self.mem = make_mem()

    def tearDown(self):
        self.mem.close()

    def _make_report(
        self, run_id="r-001", provider="default", n=10, acc=0.75, ece=0.05
    ):
        return {
            "run_id": run_id,
            "provider_tag": provider,
            "suite_name": "test_suite",
            "n_cases": n,
            "overall_accuracy": acc,
            "per_field_accuracy": {"severity": 0.8, "change_type": 0.7},
            "domain_breakdown": {"sec": acc},
            "n_fields_evaluated": {"severity": n, "change_type": n},
            "ece": ece,
            "mce": 0.1,
            "calibration": {"assessment": "ok"},
            "drift": {"summary": "stable"},
        }

    def test_store_and_retrieve(self):
        report = self._make_report()
        self.mem.store_eval_run("r-001", report)
        retrieved = self.mem.get_eval_run("r-001")
        self.assertIsNotNone(retrieved)
        self.assertAlmostEqual(retrieved["overall_accuracy"], 0.75, places=4)
        self.assertAlmostEqual(retrieved["ece"], 0.05, places=4)
        self.assertEqual(retrieved["per_field_accuracy"]["severity"], 0.8)

    def test_nonexistent_returns_none(self):
        self.assertIsNone(self.mem.get_eval_run("does-not-exist"))

    def test_list_eval_runs(self):
        self.mem.store_eval_run("r-001", self._make_report("r-001", "modelA"))
        self.mem.store_eval_run("r-002", self._make_report("r-002", "modelB"))
        runs = self.mem.list_eval_runs()
        self.assertEqual(len(runs), 2)

    def test_list_filtered_by_provider(self):
        self.mem.store_eval_run("r-001", self._make_report("r-001", "modelA"))
        self.mem.store_eval_run("r-002", self._make_report("r-002", "modelB"))
        runs = self.mem.list_eval_runs(provider_tag="modelA")
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["provider_tag"], "modelA")

    def test_compare_eval_runs(self):
        self.mem.store_eval_run("r-001", self._make_report("r-001", acc=0.70, ece=0.08))
        self.mem.store_eval_run("r-002", self._make_report("r-002", acc=0.80, ece=0.05))
        cmp = self.mem.compare_eval_runs("r-001", "r-002")
        self.assertAlmostEqual(cmp["delta_overall_accuracy"], 0.10, places=4)
        self.assertAlmostEqual(cmp["delta_ece"], -0.03, places=4)

    def test_compare_missing_run(self):
        self.mem.store_eval_run("r-001", self._make_report())
        cmp = self.mem.compare_eval_runs("r-001", "ghost")
        self.assertIn("error", cmp)


# ---------------------------------------------------------------------------
# RunEvaluationSkill
# ---------------------------------------------------------------------------


class TestRunEvaluationSkill(unittest.TestCase):
    def setUp(self):
        self.mem = make_mem()
        self.skill = RunEvaluationSkill()
        # Seed episodic + feedback
        self.mem.store_episodic(
            "F-001",
            {"id": "F-001", "title": "Capital Rule", "domain": "fed", "summary": ""},
            {
                "severity": "medium",
                "change_type": "guidance",
                "affected_business_lines": ["Capital Markets"],
                "affected_regulations": ["Basel IV"],
                "compliance_deadline": None,
                "action_items": ["Review"],
                "confidence": 0.75,
                "risk_summary": "Moderate risk",
            },
        )
        self.mem.record_feedback(
            "F-001", "severity", "medium", "high", "under-estimated"
        )

    def tearDown(self):
        self.mem.close()

    def _ctx(self, **params):
        defaults = {
            "mode": "historical",
            "provider_tag": "test-model",
            "limit": 50,
            "drift_window_days": 0,
        }
        defaults.update(params)
        return FakeContext(self.mem, defaults)

    def test_historical_mode_runs(self):
        result = self.skill.execute(self._ctx())
        self.assertTrue(result.success)
        data = result.data
        self.assertIn("run_id", data)
        self.assertIn("overall_accuracy", data)
        self.assertIn("per_field_accuracy", data)
        self.assertIn("ece", data)
        self.assertIn("calibration", data)
        self.assertIn("summary", data)

    def test_historical_mode_scores_severity(self):
        result = self.skill.execute(self._ctx())
        data = result.data
        # severity was medium, expected high → 0.0 accuracy
        self.assertIn("severity", data["per_field_accuracy"])
        self.assertAlmostEqual(data["per_field_accuracy"]["severity"], 0.0, places=4)

    def test_result_persisted_to_memory(self):
        result = self.skill.execute(self._ctx())
        run_id = result.data["run_id"]
        retrieved = self.mem.get_eval_run(run_id)
        self.assertIsNotNone(retrieved)
        self.assertAlmostEqual(
            retrieved["overall_accuracy"], result.data["overall_accuracy"], places=4
        )

    def test_empty_feedback_returns_no_cases_result(self):
        empty_mem = make_mem()
        result = self.skill.execute(
            FakeContext(
                empty_mem,
                {
                    "mode": "historical",
                    "provider_tag": "test",
                    "limit": 50,
                    "drift_window_days": 0,
                },
            )
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data["n_cases"], 0)
        empty_mem.close()

    def test_memory_denied_returns_failure(self):
        result = self.skill.execute(
            FakeContext(
                None,
                {
                    "mode": "historical",
                    "provider_tag": "test",
                    "limit": 10,
                    "drift_window_days": 0,
                },
            )
        )
        self.assertFalse(result.success)
        self.assertIn("denied", result.error.lower())

    def test_fixture_mode_missing_path_fails(self):
        result = self.skill.execute(self._ctx(mode="fixture", fixture_path=""))
        self.assertFalse(result.success)
        self.assertIn("fixture_path", result.error)

    def test_fixture_mode_invalid_path_fails(self):
        result = self.skill.execute(
            self._ctx(mode="fixture", fixture_path="/nonexistent/path/fixture.json")
        )
        self.assertFalse(result.success)

    def test_fixture_mode_valid_file(self):
        fixture = [
            {
                "case_id": "fx-001",
                "filing": {"domain": "sec", "id": "fx-001"},
                "predicted": {"severity": "high", "confidence": 0.85},
                "expected": {"severity": "high"},
                "labeled_fields": ["severity"],
            }
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            json.dump(fixture, fh)
            fh_name = fh.name
        try:
            result = self.skill.execute(self._ctx(mode="fixture", fixture_path=fh_name))
            self.assertTrue(result.success)
            self.assertEqual(result.data["n_cases"], 1)
            self.assertAlmostEqual(
                result.data["per_field_accuracy"]["severity"], 1.0, places=4
            )
        finally:
            os.unlink(fh_name)

    def test_provider_tag_in_report(self):
        result = self.skill.execute(self._ctx(provider_tag="my-model-v2"))
        self.assertEqual(result.data["provider_tag"], "my-model-v2")

    def test_custom_run_id_respected(self):
        result = self.skill.execute(self._ctx(run_id="my-custom-run-123"))
        self.assertEqual(result.data["run_id"], "my-custom-run-123")

    def test_metadata_in_result(self):
        result = self.skill.execute(self._ctx())
        self.assertIn("n_cases", result.metadata)
        self.assertIn("overall_accuracy", result.metadata)
        self.assertIn("ece", result.metadata)


if __name__ == "__main__":
    unittest.main()
