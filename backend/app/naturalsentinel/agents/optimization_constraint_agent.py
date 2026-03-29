"""OptimizationConstraintAgent — translate regulatory changes into model constraints.

Answers: "Given this new regulation, what constraints or objective function
terms need to change in our balance sheet optimizer, capital allocation model,
or portfolio construction framework?"

The most data-science-specific agent — bridges the gap between legal
regulatory text and the mathematical language of optimization models.
Designed for Lead Data Scientists running balance sheet, capital, and
portfolio optimization frameworks.
"""

from __future__ import annotations

from typing import Any

ALL_DOMAINS = [
    "sec",
    "cfpb",
    "fed",
    "fda",
    "epa",
    "ustr",
    "fhfa",
    "occ",
    "finra",
    "cftc",
    "fdic",
    "basel",
]


class OptimizationConstraintAgent:
    """
    Translates regulatory filings into formal optimization model constraints.

    Primary users: Lead Data Scientists, Quant Analysts, Capital Optimization.
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    def run(
        self,
        since_days: int = 30,
        domains: list[str] | None = None,
        include_scan: bool = True,
    ) -> dict[str, Any]:
        """Full constraint translation cycle.

        Returns:
            {constraint_analyses, hard_constraints, soft_constraints,
             objective_impacts, parameter_updates, immediate_recalibrations,
             model_types_affected, audit_summary}
        """
        target_domains = domains or ALL_DOMAINS
        if include_scan:
            self._scan(target_domains, since_days)

        analyses = self._analyze_all_filings(target_domains)

        return {
            "constraint_analyses": analyses,
            "hard_constraints": [
                a for a in analyses if a.get("constraint_type") == "hard"
            ],
            "soft_constraints": [
                a for a in analyses if a.get("constraint_type") == "soft"
            ],
            "objective_impacts": _extract_field(analyses, "objective_function_impacts"),
            "parameter_updates": _extract_field(analyses, "parameter_updates"),
            "immediate_recalibrations": [
                a for a in analyses if a.get("recalibration_urgency") == "immediate"
            ],
            "model_types_affected": _unique_model_types(analyses),
            "portfolio_impacts": _extract_field(analyses, "portfolio_impacts"),
            "audit_summary": self.runtime.audit.summary(),
        }

    def constraint_delta_report(self) -> list[dict]:
        """Return all constraint expression changes as a concise delta report."""
        analyses = self._analyze_all_filings(ALL_DOMAINS)
        report = []
        for a in analyses:
            for expr in a.get("constraint_expressions", []):
                report.append(
                    {
                        "filing_id": a.get("filing_id"),
                        "domain": a.get("domain"),
                        "constraint_name": expr.get("name"),
                        "expression": expr.get("expression_text"),
                        "direction": expr.get("constraint_direction"),
                        "binding_scenario": expr.get("binding_scenario"),
                        "models_affected": expr.get("affected_model_types", []),
                    }
                )
        return report

    def parameter_update_log(self) -> list[dict]:
        """Return all numeric parameter changes for model recalibration."""
        analyses = self._analyze_all_filings(ALL_DOMAINS)
        updates = []
        for a in analyses:
            for p in a.get("parameter_updates", []):
                updates.append(
                    {
                        "filing_id": a.get("filing_id"),
                        "domain": a.get("domain"),
                        **p,
                    }
                )
        return updates

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _scan(self, domains: list[str], since_days: int) -> dict:
        result = self.runtime.execute_skill(
            "scan_cycle", {"domains": domains, "since_days": since_days}
        )
        return result.data.get("stats", {}) if result.success else {}

    def _analyze_all_filings(self, domains: list[str]) -> list[dict]:
        records = (
            self.runtime.memory.get_filing_history(limit=100)
            if self.runtime.memory
            else []
        )
        analyses = []
        for rec in records:
            filing = rec.content.get("filing", {})
            if filing.get("domain", "") not in domains:
                continue
            result = self.runtime.execute_skill(
                "optimization_constraint", {"filing": filing}
            )
            if result.success and (
                result.data.get("constraint_expressions")
                or result.data.get("parameter_updates")
            ):
                analyses.append(result.data)
        return analyses


def _extract_field(analyses: list[dict], field: str) -> list:
    items = []
    for a in analyses:
        items.extend(a.get(field, []))
    return items


def _unique_model_types(analyses: list[dict]) -> list[str]:
    seen: set[str] = set()
    types: list[str] = []
    for a in analyses:
        for t in a.get("model_types_affected", []):
            if t not in seen:
                seen.add(t)
                types.append(t)
    return types
