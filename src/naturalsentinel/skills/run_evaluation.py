"""Skill: Run quantitative evaluation of NaturalSentinel extraction quality.

Computes three classes of metric in a single pass:

1. **Extraction accuracy** — per-field and overall accuracy against labeled
   ground truth, sourced from ``feedback_log`` corrections or a JSON fixture.

2. **Confidence calibration** — Expected Calibration Error (ECE) and Maximum
   Calibration Error (MCE) checking whether stated confidence values track
   actual accuracy.

3. **Drift analysis** — compares extraction distributions between two time
   windows to detect silent degradation or corpus shifts.

The full report is persisted to ``eval_runs`` in memory for later comparison
via :meth:`~naturalsentinel.memory.store.MemoryStore.compare_eval_runs`.

Parameters
----------
mode : str
    ``"historical"`` — derive benchmark cases from ``feedback_log``.
    ``"fixture"`` — load cases from a JSON file at ``fixture_path``.
provider_tag : str
    Label for this run (e.g. ``"claude-sonnet-4-6"``).  Used when comparing
    runs from different model configurations.
domains : list[str]
    Optional domain filter (``["sec", "fed"]``).
limit : int
    Maximum number of benchmark cases to evaluate (default 200).
fixture_path : str
    Path to a JSON fixture file (required when ``mode="fixture"``).
drift_window_days : int
    Divide episodic memory into two equal windows of this length for drift
    analysis.  Set to 0 to skip drift (default 90).
run_id : str
    Stable identifier for this run.  Auto-generated from timestamp if blank.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)
from naturalsentinel.eval.benchmark import (
    load_suite_from_feedback,
    load_suite_from_fixture,
)
from naturalsentinel.eval.calibration import build_calibration_report
from naturalsentinel.eval.drift import build_drift_report
from naturalsentinel.eval.scorer import score_suite


def _auto_run_id(provider_tag: str, suite_name: str) -> str:
    now = datetime.utcnow().isoformat()
    raw = f"{provider_tag}:{suite_name}:{now}"
    return "eval:" + hashlib.sha256(raw.encode()).hexdigest()[:12]


class RunEvaluationSkill(Skill):
    """Run a full quantitative evaluation and persist the report to memory."""

    metadata = SkillMetadata(
        name="run_evaluation",
        description=(
            "Run quantitative evaluation of NaturalSentinel extraction quality. "
            "Computes per-field extraction accuracy, confidence calibration (ECE/MCE), "
            "and drift analysis between time windows.  Sources benchmark cases from "
            "feedback_log corrections or a JSON fixture file.  Persists the report "
            "to eval_runs for longitudinal model comparison."
        ),
        version="1.0.0",
        permissions=Permission.MEMORY_READ | Permission.MEMORY_WRITE,
        latency=LatencyClass.MODERATE,
        parameters=[
            SkillParameter(
                "mode",
                "str",
                "'historical' uses feedback_log corrections as labeled examples. "
                "'fixture' loads cases from a JSON file at fixture_path.",
                required=False,
                default="historical",
            ),
            SkillParameter(
                "provider_tag",
                "str",
                "Label for this run — e.g. 'claude-sonnet-4-6' or 'gpt-4o'. "
                "Used when comparing runs from different model configurations.",
                required=False,
                default="default",
            ),
            SkillParameter(
                "domains",
                "list[str]",
                "Optional domain filter (e.g. ['sec', 'fed']). None or empty = all domains.",
                required=False,
                default=None,
            ),
            SkillParameter(
                "limit",
                "int",
                "Maximum benchmark cases to evaluate (default 200).",
                required=False,
                default=200,
            ),
            SkillParameter(
                "fixture_path",
                "str",
                "Path to a JSON fixture file. Required when mode='fixture'.",
                required=False,
                default="",
            ),
            SkillParameter(
                "drift_window_days",
                "int",
                "Days per drift window. Episodic memories are split into two "
                "consecutive windows of this length for comparison. "
                "Set to 0 to skip drift analysis (default 90).",
                required=False,
                default=90,
            ),
            SkillParameter(
                "run_id",
                "str",
                "Stable identifier for this run. Auto-generated if blank.",
                required=False,
                default="",
            ),
        ],
        returns=(
            "dict — full evaluation report with keys: run_id, provider_tag, "
            "suite_name, n_cases, overall_accuracy, per_field_accuracy, "
            "domain_breakdown, n_fields_evaluated, ece, mce, calibration, drift, "
            "run_at, summary."
        ),
        dependencies=[],
        max_token_budget=0,
        cacheable=False,
        tags=["eval", "accuracy", "calibration", "drift", "benchmark", "quality"],
    )

    def execute(self, context: SkillContext) -> SkillResult:  # noqa: C901
        if context.memory is None:
            return SkillResult(
                skill_name=self.metadata.name,
                success=False,
                data=None,
                error="Memory access denied — run_evaluation requires MEMORY_READ | MEMORY_WRITE",
            )

        mode: str = context.params.get("mode", "historical")
        provider_tag: str = context.params.get("provider_tag", "default")
        domains: list[str] | None = context.params.get("domains") or None
        limit: int = int(context.params.get("limit", 200))
        fixture_path: str = context.params.get("fixture_path", "")
        drift_window_days: int = int(context.params.get("drift_window_days", 90))
        run_id: str = context.params.get("run_id", "")

        # ------------------------------------------------------------------
        # 1. Build benchmark suite
        # ------------------------------------------------------------------
        if mode == "fixture":
            if not fixture_path:
                return SkillResult(
                    skill_name=self.metadata.name,
                    success=False,
                    data=None,
                    error="fixture_path is required when mode='fixture'",
                )
            try:
                suite = load_suite_from_fixture(fixture_path)
            except Exception as exc:
                return SkillResult(
                    skill_name=self.metadata.name,
                    success=False,
                    data=None,
                    error=f"Failed to load fixture: {exc}",
                )
        else:
            suite = load_suite_from_feedback(
                context.memory,
                domains=domains,
                limit=limit,
            )

        if not suite.cases:
            return SkillResult(
                skill_name=self.metadata.name,
                success=True,
                data={
                    "run_id": run_id or _auto_run_id(provider_tag, suite.name),
                    "provider_tag": provider_tag,
                    "suite_name": suite.name,
                    "n_cases": 0,
                    "overall_accuracy": 0.0,
                    "per_field_accuracy": {},
                    "domain_breakdown": {},
                    "n_fields_evaluated": {},
                    "ece": 0.0,
                    "mce": 0.0,
                    "calibration": {},
                    "drift": {},
                    "run_at": datetime.utcnow().isoformat(),
                    "summary": "No benchmark cases available — collect more feedback or provide a fixture.",
                },
                metadata={"n_cases": 0},
            )

        # ------------------------------------------------------------------
        # 2. Score extraction accuracy
        # ------------------------------------------------------------------
        suite_score = score_suite(suite)

        # ------------------------------------------------------------------
        # 3. Confidence calibration
        # ------------------------------------------------------------------
        calibration = build_calibration_report(suite_score.case_scores)

        calib_dict = {
            "ece": calibration.ece,
            "mce": calibration.mce,
            "n_samples": calibration.n_samples,
            "overall_accuracy": calibration.overall_accuracy,
            "overall_mean_confidence": calibration.overall_mean_confidence,
            "assessment": calibration.assessment,
            "buckets": [
                {
                    "lower": b.lower,
                    "upper": b.upper,
                    "count": b.count,
                    "mean_confidence": b.mean_confidence,
                    "mean_accuracy": b.mean_accuracy,
                    "calibration_error": b.calibration_error,
                }
                for b in calibration.buckets
            ],
        }

        # ------------------------------------------------------------------
        # 4. Drift analysis (optional)
        # ------------------------------------------------------------------
        drift_dict: dict = {}
        if drift_window_days > 0:
            try:
                drift_dict = self._compute_drift(context.memory, domains, drift_window_days)
            except Exception:
                drift_dict = {"error": "Drift analysis failed — insufficient episodic data"}

        # ------------------------------------------------------------------
        # 5. Build report and persist
        # ------------------------------------------------------------------
        final_run_id = run_id or _auto_run_id(provider_tag, suite.name)
        run_at = datetime.utcnow().isoformat()

        # Narrative summary
        n = suite_score.n_cases
        acc = suite_score.overall_accuracy
        ece = calibration.ece
        field_highlights = ", ".join(
            f"{f}={v:.2f}"
            for f, v in sorted(
                suite_score.per_field_accuracy.items(),
                key=lambda kv: kv[1],
            )
        )
        summary = (
            f"Evaluated {n} cases — overall accuracy {acc:.2%}, ECE {ece:.3f} "
            f"({calibration.assessment.split(' (')[0]}). "
            + (f"Per-field: [{field_highlights}]. " if field_highlights else "")
            + (drift_dict.get("summary", "") if drift_dict and "summary" in drift_dict else "")
        )

        report = {
            "run_id": final_run_id,
            "provider_tag": provider_tag,
            "suite_name": suite.name,
            "n_cases": suite_score.n_cases,
            "overall_accuracy": suite_score.overall_accuracy,
            "per_field_accuracy": suite_score.per_field_accuracy,
            "domain_breakdown": suite_score.domain_breakdown,
            "n_fields_evaluated": suite_score.n_fields_evaluated,
            "ece": calibration.ece,
            "mce": calibration.mce,
            "calibration": calib_dict,
            "drift": drift_dict,
            "run_at": run_at,
            "summary": summary,
        }

        context.memory.store_eval_run(final_run_id, report)

        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data=report,
            token_usage=0,
            metadata={
                "run_id": final_run_id,
                "n_cases": suite_score.n_cases,
                "overall_accuracy": suite_score.overall_accuracy,
                "ece": calibration.ece,
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_drift(memory_store, domains, window_days: int) -> dict:
        """Pull episodic memories and split into two time windows for drift."""
        all_episodes = memory_store.get_filing_history(domain=None, limit=1000)
        if domains:
            all_episodes = [r for r in all_episodes if r.namespace in domains]

        now = datetime.utcnow()
        cutoff_recent = now - timedelta(days=window_days)
        cutoff_old = now - timedelta(days=window_days * 2)

        window_b: list[dict] = []  # Recent window
        window_a: list[dict] = []  # Older window

        for rec in all_episodes:
            try:
                ts = datetime.fromisoformat(rec.created_at)
            except Exception:
                continue
            impact = rec.content.get("impact", {})
            if not impact:
                continue
            if ts >= cutoff_recent:
                window_b.append(impact)
            elif ts >= cutoff_old:
                window_a.append(impact)

        if not window_a or not window_b:
            return {
                "summary": "Insufficient episodic data for drift analysis",
                "n_window_a": len(window_a),
                "n_window_b": len(window_b),
            }

        report = build_drift_report(
            window_a,
            window_b,
            window_a_label=f"T-{window_days * 2}d to T-{window_days}d",
            window_b_label=f"T-{window_days}d to now",
        )

        return {
            "window_a_label": report.window_a_label,
            "window_b_label": report.window_b_label,
            "n_window_a": report.n_window_a,
            "n_window_b": report.n_window_b,
            "overall_drift_score": report.overall_drift_score,
            "drift_detected": report.drift_detected,
            "summary": report.summary,
            "metrics": [
                {
                    "field": m.field,
                    "shift_magnitude": m.shift_magnitude,
                    "drift_detected": m.drift_detected,
                    "description": m.description,
                }
                for m in report.metrics
            ],
        }
