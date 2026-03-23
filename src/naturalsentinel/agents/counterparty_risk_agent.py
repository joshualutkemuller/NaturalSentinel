"""CounterpartyRiskAgent — SA-CCR, IM/SIMM, and CVA capital monitoring.

Answers: "Did SA-CCR supervisory factors, initial margin models, or CVA
capital charges just change, and how does that affect our EAD, XVA pricing,
and prime brokerage counterparty limits?"

Monitors CFTC, Fed, and Basel filings for counterparty credit risk framework
changes — directly actionable for Prime Lending and XVA desks.
"""

from __future__ import annotations

from typing import Any

CCR_DOMAINS = ["cftc", "fed", "basel"]


class CounterpartyRiskAgent:
    """
    Tracks counterparty credit risk regulatory changes.

    Primary desks: Prime Lending, XVA Desk, Derivatives / Swaps.
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    def run(
        self,
        since_days: int = 30,
        include_scan: bool = True,
    ) -> dict[str, Any]:
        """Full counterparty risk monitoring cycle.

        Returns:
            {ccr_analyses, supervisory_factor_changes, im_changes,
             cva_impacts, ead_direction, xva_recalibrations, action_items,
             audit_summary}
        """
        if include_scan:
            self._scan(CCR_DOMAINS, since_days)

        analyses = self._analyze_ccr_filings()

        return {
            "ccr_analyses": analyses,
            "supervisory_factor_changes": _extract_sf_changes(analyses),
            "im_changes": [
                {
                    "filing_id": a.get("filing_id"),
                    "change_pct": a.get("initial_margin_change_pct", 0),
                }
                for a in analyses
                if a.get("initial_margin_change_pct", 0) != 0
            ],
            "cva_impacts": [
                a.get("cva_capital_impact")
                for a in analyses
                if a.get("cva_capital_impact") not in (None, "neutral")
            ],
            "ead_direction": [
                {"filing_id": a.get("filing_id"), "direction": a.get("ead_delta_direction")}
                for a in analyses
                if a.get("ead_delta_direction") not in (None, "neutral")
            ],
            "xva_recalibrations": [a for a in analyses if a.get("xva_recalibration_required")],
            "action_items": _dedup(analyses, "action_items"),
            "audit_summary": self.runtime.audit.summary(),
        }

    def ead_reducing_opportunities(self) -> list[dict]:
        """Return analyses where regulatory changes allow EAD reduction (e.g. 0% SF qualification)."""
        analyses = self._analyze_ccr_filings()
        return [a for a in analyses if a.get("ead_delta_direction") in ("decrease", "reduction")]

    def im_increase_summary(self) -> dict:
        """Aggregate IM change percentages across all current analyses."""
        analyses = self._analyze_ccr_filings()
        changes = [a.get("initial_margin_change_pct", 0) for a in analyses]
        if not changes:
            return {"count": 0, "avg_change_pct": 0.0, "max_change_pct": 0.0}
        return {
            "count": len(changes),
            "avg_change_pct": sum(changes) / len(changes),
            "max_change_pct": max(changes),
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _scan(self, domains: list[str], since_days: int) -> dict:
        result = self.runtime.execute_skill(
            "scan_cycle", {"domains": domains, "since_days": since_days}
        )
        return result.data.get("stats", {}) if result.success else {}

    def _analyze_ccr_filings(self) -> list[dict]:
        records = self.runtime.memory.get_filing_history(limit=50) if self.runtime.memory else []
        analyses = []
        for rec in records:
            filing = rec.content.get("filing", {})
            if filing.get("domain", "") not in CCR_DOMAINS:
                continue
            result = self.runtime.execute_skill("counterparty_risk_analysis", {"filing": filing})
            if result.success:
                analyses.append(result.data)
        return analyses


def _extract_sf_changes(analyses: list[dict]) -> list[dict]:
    changes = []
    for a in analyses:
        for sf in a.get("supervisory_factor_changes", []):
            changes.append({"filing_id": a.get("filing_id"), **sf})
    return changes


def _dedup(analyses: list[dict], field: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for a in analyses:
        for item in a.get(field, []):
            if item not in seen:
                seen.add(item)
                result.append(item)
    return result
