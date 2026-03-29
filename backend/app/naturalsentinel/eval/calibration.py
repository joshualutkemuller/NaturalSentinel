"""Confidence calibration analysis.

A well-calibrated model that predicts ``confidence=0.80`` should be correct
approximately 80% of the time on those predictions.  This module measures
how well NaturalSentinel's stated confidence values track actual accuracy.

Metrics produced
----------------
ECE  Expected Calibration Error — weighted mean of |accuracy - confidence|
     across all non-empty confidence buckets.  Lower is better.
     ECE < 0.05  →  well-calibrated
     ECE < 0.10  →  moderately calibrated
     ECE >= 0.20 →  severely miscalibrated

MCE  Maximum Calibration Error — worst-case bucket gap.

Reliability diagram data is included in each :class:`CalibrationBucket` so
callers can render a plot if desired.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CalibrationBucket:
    lower: float  # Bucket lower bound (inclusive)
    upper: float  # Bucket upper bound (exclusive)
    count: int  # Predictions in this bucket
    mean_confidence: float  # Mean predicted confidence
    mean_accuracy: float  # Fraction of cases correct (score >= 0.5)
    calibration_error: float  # |mean_accuracy − mean_confidence|


@dataclass
class CalibrationReport:
    buckets: list[CalibrationBucket] = field(default_factory=list)
    ece: float = 0.0
    mce: float = 0.0
    n_samples: int = 0
    overall_accuracy: float = 0.0
    overall_mean_confidence: float = 0.0
    assessment: str = ""


def build_calibration_report(
    case_scores: list,
    n_buckets: int = 10,
) -> CalibrationReport:
    """Compute a calibration report from a list of :class:`~naturalsentinel.eval.scorer.CaseScore` objects.

    A prediction is counted as *correct* when ``overall_score >= 0.5``.

    Args:
        case_scores: Output of :func:`~naturalsentinel.eval.scorer.score_suite`.
        n_buckets: Number of equal-width confidence buckets (default 10 → width 0.1).

    Returns:
        A :class:`CalibrationReport` with per-bucket stats, ECE, MCE,
        and a human-readable assessment string.
    """
    if not case_scores:
        return CalibrationReport(assessment="No data — cannot compute calibration")

    bucket_width = 1.0 / n_buckets
    # Each bucket: list of (confidence, is_correct)
    raw_buckets: list[list[tuple[float, float]]] = [[] for _ in range(n_buckets)]

    for cs in case_scores:
        conf = min(max(float(cs.confidence), 0.0), 0.9999)
        bucket_idx = min(int(conf / bucket_width), n_buckets - 1)
        is_correct = 1.0 if cs.overall_score >= 0.5 else 0.0
        raw_buckets[bucket_idx].append((conf, is_correct))

    buckets: list[CalibrationBucket] = []
    for i, items in enumerate(raw_buckets):
        if not items:
            continue
        lower = i * bucket_width
        upper = (i + 1) * bucket_width
        mean_conf = sum(c for c, _ in items) / len(items)
        mean_acc = sum(a for _, a in items) / len(items)
        err = abs(mean_acc - mean_conf)
        buckets.append(
            CalibrationBucket(
                lower=round(lower, 2),
                upper=round(upper, 2),
                count=len(items),
                mean_confidence=round(mean_conf, 4),
                mean_accuracy=round(mean_acc, 4),
                calibration_error=round(err, 4),
            )
        )

    n_total = sum(len(items) for items in raw_buckets)
    ece = (
        sum(b.count * b.calibration_error for b in buckets) / n_total
        if n_total > 0
        else 0.0
    )
    mce = max((b.calibration_error for b in buckets), default=0.0)

    all_scores = [cs.overall_score for cs in case_scores]
    overall_accuracy = sum(1.0 for s in all_scores if s >= 0.5) / len(all_scores)
    overall_conf = sum(cs.confidence for cs in case_scores) / len(case_scores)

    if ece < 0.05:
        assessment = "Well-calibrated (ECE < 0.05)"
    elif ece < 0.10:
        assessment = "Moderately calibrated (ECE 0.05–0.10)"
    elif ece < 0.20:
        assessment = "Poorly calibrated (ECE 0.10–0.20) — confidence tuning recommended"
    else:
        assessment = "Severely miscalibrated (ECE ≥ 0.20) — systemic over/under-confidence detected"

    return CalibrationReport(
        buckets=buckets,
        ece=round(ece, 4),
        mce=round(mce, 4),
        n_samples=n_total,
        overall_accuracy=round(overall_accuracy, 4),
        overall_mean_confidence=round(overall_conf, 4),
        assessment=assessment,
    )
