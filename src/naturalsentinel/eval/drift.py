"""Extraction drift analysis across time windows.

Compares the distribution of model outputs between two time periods to detect
whether the corpus, prompts, or model behaviour have shifted meaningfully.

Use cases
---------
- Detecting silent model degradation after a provider update.
- Identifying changes in the regulatory corpus (e.g. sudden spike in CRITICAL
  severity filings).
- Validating that prompt changes do not shift calibration.

Fields analysed
---------------
severity              Categorical — total variation distance
confidence            Numeric — Cohen's d-style effect size
affected_business_lines  Categorical (multi-value) — TV distance on frequency
change_type           Categorical — TV distance

Drift is flagged when the shift metric exceeds ``drift_threshold`` (default 0.15).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class DriftMetric:
    field: str
    window_a_stats: dict
    window_b_stats: dict
    shift_magnitude: float  # 0.0–1.0 normalised distance
    drift_detected: bool
    description: str = ""


@dataclass
class DriftReport:
    window_a_label: str
    window_b_label: str
    metrics: list[DriftMetric] = field(default_factory=list)
    overall_drift_score: float = 0.0
    drift_detected: bool = False
    n_window_a: int = 0
    n_window_b: int = 0
    summary: str = ""


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------


def _categorical_distribution(values: list[str]) -> dict[str, float]:
    """Normalised frequency distribution of categorical values."""
    counts: dict[str, int] = {}
    for v in values:
        key = str(v).lower().strip()
        counts[key] = counts.get(key, 0) + 1
    total = sum(counts.values()) or 1
    return {k: round(v / total, 4) for k, v in counts.items()}


def _tv_distance(dist_a: dict[str, float], dist_b: dict[str, float]) -> float:
    """Total variation distance between two discrete distributions (0–1)."""
    all_keys = set(dist_a) | set(dist_b)
    return 0.5 * sum(abs(dist_a.get(k, 0.0) - dist_b.get(k, 0.0)) for k in all_keys)


def _numeric_stats(values: list[float]) -> dict:
    n = len(values)
    if n == 0:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "n": 0}
    mean = sum(values) / n
    std = math.sqrt(sum((x - mean) ** 2 for x in values) / n)
    return {
        "mean": round(mean, 4),
        "std": round(std, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "n": n,
    }


def _effect_size(stats_a: dict, stats_b: dict) -> float:
    """Cohen's d-style effect size clamped to [0, 1].

    A pooled standard deviation of 0 returns 0.0 if means agree, else 1.0.
    A Cohen's d of 2.0 maps to 1.0 (extreme shift).
    """
    pooled_std = (stats_a["std"] + stats_b["std"]) / 2.0
    if pooled_std == 0.0:
        return 0.0 if stats_a["mean"] == stats_b["mean"] else 1.0
    d = abs(stats_a["mean"] - stats_b["mean"]) / pooled_std
    return min(d / 2.0, 1.0)  # d=2 → 1.0


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


def build_drift_report(
    window_a: list[dict],
    window_b: list[dict],
    window_a_label: str = "Window A",
    window_b_label: str = "Window B",
    drift_threshold: float = 0.15,
) -> DriftReport:
    """Compare extraction distributions between two analysis windows.

    Args:
        window_a: List of impact assessment dicts from the earlier period.
        window_b: List of impact assessment dicts from the later period.
        window_a_label: Human-readable label for window A (e.g. "2025-Q3").
        window_b_label: Human-readable label for window B (e.g. "2026-Q1").
        drift_threshold: Shift magnitude above which drift is flagged (default 0.15).

    Returns:
        A :class:`DriftReport` with per-field metrics, overall drift score,
        and a summary string.
    """
    metrics: list[DriftMetric] = []

    # --- Severity ---
    sev_a = [d["severity"] for d in window_a if d.get("severity")]
    sev_b = [d["severity"] for d in window_b if d.get("severity")]
    if sev_a and sev_b:
        dist_a = _categorical_distribution(sev_a)
        dist_b = _categorical_distribution(sev_b)
        tv = _tv_distance(dist_a, dist_b)
        metrics.append(
            DriftMetric(
                field="severity",
                window_a_stats={"distribution": dist_a, "n": len(sev_a)},
                window_b_stats={"distribution": dist_b, "n": len(sev_b)},
                shift_magnitude=round(tv, 4),
                drift_detected=tv > drift_threshold,
                description=(
                    f"Severity distribution shifted (TV={tv:.3f})"
                    if tv > drift_threshold
                    else f"Severity distribution stable (TV={tv:.3f})"
                ),
            )
        )

    # --- Confidence ---
    conf_a = [float(d["confidence"]) for d in window_a if d.get("confidence") is not None]
    conf_b = [float(d["confidence"]) for d in window_b if d.get("confidence") is not None]
    if conf_a and conf_b:
        stats_a = _numeric_stats(conf_a)
        stats_b = _numeric_stats(conf_b)
        effect = _effect_size(stats_a, stats_b)
        metrics.append(
            DriftMetric(
                field="confidence",
                window_a_stats=stats_a,
                window_b_stats=stats_b,
                shift_magnitude=round(effect, 4),
                drift_detected=effect > drift_threshold,
                description=(
                    f"Confidence mean shifted from {stats_a['mean']:.3f} "
                    f"to {stats_b['mean']:.3f} (effect={effect:.3f})"
                ),
            )
        )

    # --- Business lines (frequency of mention) ---
    def _flatten_lists(records: list[dict], key: str) -> list[str]:
        result: list[str] = []
        for r in records:
            result.extend(str(x).lower() for x in (r.get(key) or []))
        return result

    lines_a = _flatten_lists(window_a, "affected_business_lines")
    lines_b = _flatten_lists(window_b, "affected_business_lines")
    if lines_a and lines_b:
        dist_a = _categorical_distribution(lines_a)
        dist_b = _categorical_distribution(lines_b)
        tv = _tv_distance(dist_a, dist_b)
        metrics.append(
            DriftMetric(
                field="affected_business_lines",
                window_a_stats={"distribution": dist_a, "n": len(lines_a)},
                window_b_stats={"distribution": dist_b, "n": len(lines_b)},
                shift_magnitude=round(tv, 4),
                drift_detected=tv > drift_threshold,
                description=(
                    f"Business line mention frequency shifted (TV={tv:.3f})"
                    if tv > drift_threshold
                    else f"Business line distribution stable (TV={tv:.3f})"
                ),
            )
        )

    # --- Change type ---
    ct_a = [d["change_type"] for d in window_a if d.get("change_type")]
    ct_b = [d["change_type"] for d in window_b if d.get("change_type")]
    if ct_a and ct_b:
        dist_a = _categorical_distribution(ct_a)
        dist_b = _categorical_distribution(ct_b)
        tv = _tv_distance(dist_a, dist_b)
        metrics.append(
            DriftMetric(
                field="change_type",
                window_a_stats={"distribution": dist_a},
                window_b_stats={"distribution": dist_b},
                shift_magnitude=round(tv, 4),
                drift_detected=tv > drift_threshold,
                description=(
                    f"Change-type distribution shifted (TV={tv:.3f})"
                    if tv > drift_threshold
                    else f"Change-type distribution stable (TV={tv:.3f})"
                ),
            )
        )

    detected = [m for m in metrics if m.drift_detected]
    overall = round(sum(m.shift_magnitude for m in metrics) / len(metrics), 4) if metrics else 0.0

    if not metrics:
        summary = "Insufficient data for drift analysis"
    elif detected:
        summary = f"Drift detected in {len(detected)}/{len(metrics)} fields: " + ", ".join(
            m.field for m in detected
        )
    else:
        summary = f"No significant drift across {len(metrics)} fields"

    return DriftReport(
        window_a_label=window_a_label,
        window_b_label=window_b_label,
        metrics=metrics,
        overall_drift_score=overall,
        drift_detected=bool(detected),
        n_window_a=len(window_a),
        n_window_b=len(window_b),
        summary=summary,
    )
