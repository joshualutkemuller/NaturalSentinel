"""LeveragedLendingAgent — leveraged lending guidance and CLO rule monitoring.

Answers: "Are our leveraged lending underwriting criteria still within OCC/Fed
guidance? Did leverage thresholds, covenant requirements, or CLO risk retention
rules change?"

Monitors OCC, Fed, and FDIC filings for leveraged lending guidance updates
and maps them to portfolio exceptions, documentation requirements, and
supervisory review triggers for Secured Lending and Financing Solutions desks.
"""
from __future__ import annotations
from typing import Any

LL_DOMAINS = ["occ", "fed", "fdic"]


class LeveragedLendingAgent:
    """
    Monitors leveraged lending regulatory environment.

    Primary desks: Secured Lending, Financing Solutions, Credit Portfolio.
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    def run(
        self,
        since_days: int = 30,
        portfolio_leverage_ratio: float | None = None,
        include_scan: bool = True,
    ) -> dict[str, Any]:
        """Full leveraged lending monitoring cycle.

        Args:
            portfolio_leverage_ratio: Current portfolio average debt/EBITDA, used
                to assess proximity to supervisory review triggers.

        Returns:
            {ll_analyses, threshold_changes, covenant_changes,
             supervisory_triggers, portfolio_exceptions, credit_policy_updates,
             audit_summary}
        """
        if include_scan:
            self._scan(LL_DOMAINS, since_days)

        analyses = self._analyze_ll_filings()
        triggers = _extract_field(analyses, "supervisory_review_triggers")

        return {
            "ll_analyses": analyses,
            "threshold_changes": _extract_threshold_changes(analyses),
            "covenant_changes": _extract_field(analyses, "covenant_requirement_changes"),
            "definition_changes": _extract_field(analyses, "definition_changes"),
            "supervisory_triggers": triggers,
            "portfolio_at_risk": _assess_portfolio_risk(triggers, portfolio_leverage_ratio),
            "credit_policy_updates": _extract_field(analyses, "credit_policy_updates_required"),
            "documentation_requirements": _extract_field(analyses, "documentation_requirements"),
            "audit_summary": self.runtime.audit.summary(),
        }

    def exception_report(self) -> list[dict]:
        """Return portfolio classification impacts that may create policy exceptions."""
        analyses = self._analyze_ll_filings()
        exceptions = []
        for a in analyses:
            for impact in a.get("portfolio_classification_impacts", []):
                exceptions.append({
                    "filing_id": a.get("filing_id"),
                    "domain": a.get("domain"),
                    "impact": impact,
                })
        return exceptions

    def new_supervisory_review_threshold(self) -> float | None:
        """Return the most restrictive new leverage ratio supervisory review trigger."""
        analyses = self._analyze_ll_filings()
        thresholds = []
        for a in analyses:
            for t in a.get("leverage_threshold_changes", []):
                try:
                    thresholds.append(float(str(t.get("new_threshold", "")).replace("x", "")))
                except (ValueError, TypeError):
                    pass
        return min(thresholds) if thresholds else None

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _scan(self, domains: list[str], since_days: int) -> dict:
        result = self.runtime.execute_skill("scan_cycle", {"domains": domains, "since_days": since_days})
        return result.data.get("stats", {}) if result.success else {}

    def _analyze_ll_filings(self) -> list[dict]:
        records = self.runtime.memory.get_filing_history(limit=50) if self.runtime.memory else []
        analyses = []
        for rec in records:
            filing = rec.content.get("filing", {})
            if filing.get("domain", "") not in LL_DOMAINS:
                continue
            result = self.runtime.execute_skill("leveraged_lending_assessment", {"filing": filing})
            if result.success:
                analyses.append(result.data)
        return analyses


def _extract_field(analyses: list[dict], field: str) -> list:
    items = []
    for a in analyses:
        items.extend(a.get(field, []))
    return items


def _extract_threshold_changes(analyses: list[dict]) -> list[dict]:
    changes = []
    for a in analyses:
        for t in a.get("leverage_threshold_changes", []):
            changes.append({"filing_id": a.get("filing_id"), **t})
    return changes


def _assess_portfolio_risk(triggers: list, portfolio_ratio: float | None) -> str:
    if portfolio_ratio is None or not triggers:
        return "unknown"
    trigger_text = " ".join(str(t) for t in triggers).lower()
    if "3x" in trigger_text or "three times" in trigger_text:
        return "elevated" if portfolio_ratio > 2.5 else "normal"
    return "normal"
