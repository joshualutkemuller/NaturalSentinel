"""Quantitative evaluation layer for NaturalSentinel.

Modules
-------
benchmark    BenchmarkCase / BenchmarkSuite construction from feedback_log or fixtures
scorer       Per-field extraction accuracy (exact match, Jaccard, date match, count ratio)
calibration  Confidence calibration analysis (ECE, MCE, reliability diagram data)
drift        Extraction distribution drift between time windows (TV distance, Cohen's d)
"""

from naturalsentinel.eval.benchmark import (
    BenchmarkCase,
    BenchmarkSuite,
    load_suite_from_feedback,
    load_suite_from_fixture,
)
from naturalsentinel.eval.scorer import (
    FieldScore,
    CaseScore,
    SuiteScore,
    score_field,
    score_case,
    score_suite,
    CATEGORICAL_FIELDS,
    SET_FIELDS,
    DATE_FIELDS,
    COUNT_FIELDS,
    ALL_SCORED_FIELDS,
)
from naturalsentinel.eval.calibration import (
    CalibrationBucket,
    CalibrationReport,
    build_calibration_report,
)
from naturalsentinel.eval.drift import (
    DriftMetric,
    DriftReport,
    build_drift_report,
)

__all__ = [
    # Benchmark
    "BenchmarkCase",
    "BenchmarkSuite",
    "load_suite_from_feedback",
    "load_suite_from_fixture",
    # Scorer
    "FieldScore",
    "CaseScore",
    "SuiteScore",
    "score_field",
    "score_case",
    "score_suite",
    "CATEGORICAL_FIELDS",
    "SET_FIELDS",
    "DATE_FIELDS",
    "COUNT_FIELDS",
    "ALL_SCORED_FIELDS",
    # Calibration
    "CalibrationBucket",
    "CalibrationReport",
    "build_calibration_report",
    # Drift
    "DriftMetric",
    "DriftReport",
    "build_drift_report",
]
