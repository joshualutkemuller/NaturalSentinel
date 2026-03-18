"""CapitalOptimizationAgent — capital impact monitoring for lending and trading desks.

Answers: "How does this regulatory change affect our capital cost per trade,
RWA calculations, and optimization model constraints?"

Monitors Fed, OCC, FDIC, and Basel filings for capital rule changes and
translates them into quantitative impacts on RWA, SLR, leverage ratio,
and output floor constraints — directly feeding capital allocation models.
"""
from __future__ import annotations
from typing import Any

CAPITAL_DOMAINS = ["fed", "occ", "fdic", "basel"]


class CapitalOptimizationAgent:
    """
    Monitors capital regulation and surfaces optimization model impacts.

    Primary desks: Capital Optimization, RWA Modelling, XVA, All Lending Desks.
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    def run(
        self,
        since_days: int = 30,
        domains: list[str] | None = None,
        include_scan: bool = True,
    ) -> dict[str, Any]:
        """Full capital monitoring cycle.

        Returns:
            {capital_analyses, rwa_alerts, optimization_impacts,
             audit_summary, scan_stats}
        """
        scan_stats: dict = {}
        if include_scan:
            scan_stats = self._scan(domains or CAPITAL_DOMAINS, since_days)

        analyses = self._analyze_capital_filings(domains or CAPITAL_DOMAINS)
        rwa_alerts = self._get_alerts(threshold="high", domains=domains or CAPITAL_DOMAINS)

        return {
            "capital_analyses": analyses,
            "rwa_alerts": rwa_alerts,
            "optimization_impacts": _extract_optimization_impacts(analyses),
            "audit_summary": self.runtime.audit.summary(),
            "scan_stats": scan_stats,
        }

    def model_recalibrations_required(self) -> list[dict]:
        """Return filings that require capital model recalibration."""
        analyses = self._analyze_capital_filings(CAPITAL_DOMAINS)
        return [a for a in analyses if a.get("model_recalibration_required")]

    def constraint_changes(self) -> list[dict]:
        """Return optimization constraint changes from all capital analyses."""
        analyses = self._analyze_capital_filings(CAPITAL_DOMAINS)
        changes = []
        for a in analyses:
            for c in a.get("optimization_constraint_changes", []):
                changes.append({"filing_id": a.get("filing_id"), "constraint": c})
        return changes

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _scan(self, domains: list[str], since_days: int) -> dict:
        result = self.runtime.execute_skill("scan_cycle", {"domains": domains, "since_days": since_days})
        return result.data.get("stats", {}) if result.success else {"error": result.error}

    def _analyze_capital_filings(self, domains: list[str]) -> list[dict]:
        records = self.runtime.memory.get_filing_history(limit=50) if self.runtime.memory else []
        analyses = []
        for rec in records:
            filing = rec.content.get("filing", {})
            if filing.get("domain", "") not in domains:
                continue
            result = self.runtime.execute_skill("capital_impact", {"filing": filing})
            if result.success:
                analyses.append(result.data)
        return analyses

    def _get_alerts(self, threshold: str, domains: list[str]) -> list[dict]:
        result = self.runtime.execute_skill("alert_threshold", {"threshold": threshold, "limit": 100})
        if not result.success:
            return []
        return [a for a in result.data.get("alerts", []) if a.get("domain", "").lower() in domains]


def _extract_optimization_impacts(analyses: list[dict]) -> list[dict]:
    impacts = []
    for a in analyses:
        for c in a.get("optimization_constraint_changes", []):
            impacts.append({
                "filing_id": a.get("filing_id"),
                "domain": a.get("domain"),
                "constraint": c,
                "rwa_direction": a.get("rwa_impact_direction"),
                "capital_cost_bps": a.get("capital_cost_per_trade_bps", 0),
            })
    return impacts
