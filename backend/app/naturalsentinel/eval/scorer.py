"""Per-field extraction accuracy scoring.

Scoring functions are chosen by field type:

+---------------------------------+-------------------+------------------------------------+
| Field                           | Metric            | Notes                              |
+=================================+===================+====================================+
| severity, change_type           | exact_match       | Case-insensitive string equality   |
+---------------------------------+-------------------+------------------------------------+
| affected_business_lines,        | jaccard           | Set-level overlap (order ignored)  |
| affected_regulations            |                   |                                    |
+---------------------------------+-------------------+------------------------------------+
| compliance_deadline             | date_match        | Exact or both-null                 |
+---------------------------------+-------------------+------------------------------------+
| action_items                    | count_ratio       | min/max of list lengths            |
+---------------------------------+-------------------+------------------------------------+

Any field not in the above map scores 0.5 (neutral / unknown).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Field taxonomy
# ---------------------------------------------------------------------------

CATEGORICAL_FIELDS: frozenset[str] = frozenset({"severity", "change_type"})
SET_FIELDS: frozenset[str] = frozenset(
    {"affected_business_lines", "affected_regulations"}
)
DATE_FIELDS: frozenset[str] = frozenset({"compliance_deadline"})
COUNT_FIELDS: frozenset[str] = frozenset({"action_items"})

ALL_SCORED_FIELDS: frozenset[str] = (
    CATEGORICAL_FIELDS | SET_FIELDS | DATE_FIELDS | COUNT_FIELDS
)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FieldScore:
    field: str
    score: float  # 0.0–1.0
    predicted: object = None
    expected: object = None
    metric: str = ""  # "exact_match" | "jaccard" | "date_match" | "count_ratio"


@dataclass
class CaseScore:
    case_id: str
    field_scores: list[FieldScore] = field(default_factory=list)
    overall_score: float = 0.0
    domain: str = ""
    confidence: float = 0.0  # Model's stated confidence (for calibration)


@dataclass
class SuiteScore:
    suite_name: str
    case_scores: list[CaseScore] = field(default_factory=list)
    per_field_accuracy: dict[str, float] = field(default_factory=dict)
    overall_accuracy: float = 0.0
    n_cases: int = 0
    n_fields_evaluated: dict[str, int] = field(default_factory=dict)
    domain_breakdown: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def _norm(val: object) -> str:
    return str(val).lower().strip() if val is not None else ""


def _jaccard(pred: list, expected: list) -> float:
    if not pred and not expected:
        return 1.0
    if not pred or not expected:
        return 0.0
    pred_set = {_norm(x) for x in pred}
    exp_set = {_norm(x) for x in expected}
    intersection = pred_set & exp_set
    union = pred_set | exp_set
    return len(intersection) / len(union) if union else 0.0


# ---------------------------------------------------------------------------
# Field-level scoring
# ---------------------------------------------------------------------------


def score_field(
    field_name: str, predicted_val: object, expected_val: object
) -> FieldScore:
    """Score a single (field_name, predicted, expected) triple."""

    if field_name in CATEGORICAL_FIELDS:
        match = _norm(predicted_val) == _norm(expected_val)
        return FieldScore(
            field=field_name,
            score=1.0 if match else 0.0,
            predicted=predicted_val,
            expected=expected_val,
            metric="exact_match",
        )

    if field_name in SET_FIELDS:
        score = _jaccard(predicted_val or [], expected_val or [])
        return FieldScore(
            field=field_name,
            score=score,
            predicted=predicted_val,
            expected=expected_val,
            metric="jaccard",
        )

    if field_name in DATE_FIELDS:
        if predicted_val is None and expected_val is None:
            score = 1.0
        elif predicted_val is None or expected_val is None:
            score = 0.0
        else:
            score = (
                1.0 if str(predicted_val).strip() == str(expected_val).strip() else 0.0
            )
        return FieldScore(
            field=field_name,
            score=score,
            predicted=predicted_val,
            expected=expected_val,
            metric="date_match",
        )

    if field_name in COUNT_FIELDS:
        pred_n = len(predicted_val) if isinstance(predicted_val, list) else 0
        exp_n = len(expected_val) if isinstance(expected_val, list) else 0
        if pred_n == 0 and exp_n == 0:
            score = 1.0
        else:
            score = min(pred_n, exp_n) / max(pred_n, exp_n, 1)
        return FieldScore(
            field=field_name,
            score=score,
            predicted=pred_n,
            expected=exp_n,
            metric="count_ratio",
        )

    # Unknown field — neutral score, still recorded
    return FieldScore(
        field=field_name,
        score=0.5,
        predicted=predicted_val,
        expected=expected_val,
        metric="unknown",
    )


# ---------------------------------------------------------------------------
# Case and suite scoring
# ---------------------------------------------------------------------------


def score_case(case) -> CaseScore:
    """Score a single :class:`~naturalsentinel.eval.benchmark.BenchmarkCase`."""
    field_scores: list[FieldScore] = []
    for f in case.labeled_fields:
        expected_val = case.expected.get(f)
        if expected_val is None:
            continue  # No ground truth — skip
        predicted_val = case.predicted.get(f)
        field_scores.append(score_field(f, predicted_val, expected_val))

    overall = (
        sum(fs.score for fs in field_scores) / len(field_scores)
        if field_scores
        else 0.0
    )
    confidence = float(case.predicted.get("confidence", 0.0))

    return CaseScore(
        case_id=case.case_id,
        field_scores=field_scores,
        overall_score=round(overall, 4),
        domain=case.filing.get("domain", ""),
        confidence=confidence,
    )


def score_suite(suite) -> SuiteScore:
    """Score all cases in a :class:`~naturalsentinel.eval.benchmark.BenchmarkSuite`."""
    case_scores = [score_case(c) for c in suite.cases]

    # Per-field aggregation
    per_field: dict[str, list[float]] = {}
    per_field_count: dict[str, int] = {}
    for cs in case_scores:
        for fs in cs.field_scores:
            per_field.setdefault(fs.field, []).append(fs.score)
            per_field_count[fs.field] = per_field_count.get(fs.field, 0) + 1

    per_field_accuracy = {
        f: round(sum(scores) / len(scores), 4) for f, scores in per_field.items()
    }

    # Domain breakdown
    domain_scores: dict[str, list[float]] = {}
    for cs in case_scores:
        domain_scores.setdefault(cs.domain, []).append(cs.overall_score)
    domain_breakdown = {d: round(sum(s) / len(s), 4) for d, s in domain_scores.items()}

    overall_accuracy = (
        round(sum(cs.overall_score for cs in case_scores) / len(case_scores), 4)
        if case_scores
        else 0.0
    )

    return SuiteScore(
        suite_name=suite.name,
        case_scores=case_scores,
        per_field_accuracy=per_field_accuracy,
        overall_accuracy=overall_accuracy,
        n_cases=len(case_scores),
        n_fields_evaluated=per_field_count,
        domain_breakdown=domain_breakdown,
    )
