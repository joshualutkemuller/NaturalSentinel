"""LiquidityRatioAgent — LCR, NSFR, and HQLA classification monitoring.

Answers: "Did HQLA treatment change for any assets we hold, and how does
that affect our LCR/NSFR ratios and balance sheet optimization constraints?"

Monitors Fed, FDIC, and Basel filings for liquidity coverage and net stable
funding ratio changes — directly feeding balance sheet optimization models
and ALM constraint frameworks for Financing Solutions desks.
"""

from __future__ import annotations

from typing import Any

LIQ_DOMAINS = ["fed", "fdic", "basel"]


class LiquidityRatioAgent:
    """
    Tracks liquidity regulation changes and their ALM model implications.

    Primary desks: Financing Solutions, Treasury & ALM, Capital Optimization.
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    def run(
        self,
        since_days: int = 30,
        include_scan: bool = True,
    ) -> dict[str, Any]:
        """Full liquidity monitoring cycle.

        Returns:
            {liquidity_analyses, hqla_reclassifications, lcr_impacts,
             nsfr_impacts, alm_constraint_changes, funding_cost_impacts,
             audit_summary}
        """
        if include_scan:
            self._scan(LIQ_DOMAINS, since_days)

        analyses = self._analyze_liquidity_filings()

        return {
            "liquidity_analyses": analyses,
            "hqla_reclassifications": _extract_hqla_changes(analyses),
            "lcr_impacts": [
                {
                    "filing_id": a.get("filing_id"),
                    "direction": a.get("lcr_impact_direction"),
                    "delta_pct": a.get("lcr_delta_estimate_pct", 0),
                }
                for a in analyses
                if a.get("lcr_impact_direction") != "neutral"
            ],
            "nsfr_impacts": [
                {
                    "filing_id": a.get("filing_id"),
                    "direction": a.get("nsfr_impact_direction"),
                    "changes": a.get("nsfr_asf_rsf_changes", []),
                }
                for a in analyses
                if a.get("nsfr_impact_direction") != "neutral"
            ],
            "alm_constraint_changes": _extract_field(
                analyses, "balance_sheet_optimization_constraints"
            ),
            "funding_cost_impacts": [
                {"filing_id": a.get("filing_id"), "impact": a.get("funding_cost_impact")}
                for a in analyses
                if a.get("funding_cost_impact") not in (None, "neutral")
            ],
            "audit_summary": self.runtime.audit.summary(),
        }

    def binding_lcr_constraints(self) -> list[dict]:
        """Return LCR changes that are likely to bind optimization models."""
        analyses = self._analyze_liquidity_filings()
        return [
            a
            for a in analyses
            if a.get("lcr_impact_direction") in ("tightening", "increase")
            and a.get("balance_sheet_optimization_constraints")
        ]

    def hqla_downgrades(self) -> list[dict]:
        """Return HQLA reclassifications where assets move to a lower liquidity tier."""
        changes = _extract_hqla_changes(self._analyze_liquidity_filings())
        return [c for c in changes if _is_downgrade(c.get("old_level", ""), c.get("new_level", ""))]

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _scan(self, domains: list[str], since_days: int) -> dict:
        result = self.runtime.execute_skill(
            "scan_cycle", {"domains": domains, "since_days": since_days}
        )
        return result.data.get("stats", {}) if result.success else {}

    def _analyze_liquidity_filings(self) -> list[dict]:
        records = self.runtime.memory.get_filing_history(limit=50) if self.runtime.memory else []
        analyses = []
        for rec in records:
            filing = rec.content.get("filing", {})
            if filing.get("domain", "") not in LIQ_DOMAINS:
                continue
            result = self.runtime.execute_skill("liquidity_ratio_analysis", {"filing": filing})
            if result.success:
                analyses.append(result.data)
        return analyses


def _extract_hqla_changes(analyses: list[dict]) -> list[dict]:
    changes = []
    for a in analyses:
        for c in a.get("hqla_classification_changes", []):
            changes.append({"filing_id": a.get("filing_id"), **c})
    return changes


def _extract_field(analyses: list[dict], field: str) -> list:
    items = []
    for a in analyses:
        items.extend(a.get(field, []))
    return items


def _is_downgrade(old: str, new: str) -> bool:
    tier_rank = {"level_1": 3, "level_2a": 2, "level_2b": 1, "non_hqla": 0}
    return tier_rank.get(new.lower().replace(" ", "_"), 0) < tier_rank.get(
        old.lower().replace(" ", "_"), 0
    )
