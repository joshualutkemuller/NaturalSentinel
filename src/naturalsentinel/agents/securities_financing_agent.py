"""SecuritiesFinancingAgent — repo, securities lending, and TBA monitoring.

Answers: "What changed in the rules governing our repo book, securities
lending program, or TBA trading, and what do we need to do?"

Monitors SEC, Fed, and FINRA filings for changes to collateral schedules,
haircut matrices, rehypothecation limits, margin rules, and SFTR reporting —
actionable for Secured Lending, Agency Lending, and Prime desks.
"""
from __future__ import annotations
from typing import Any

SF_DOMAINS = ["sec", "fed", "finra"]


class SecuritiesFinancingAgent:
    """
    Monitors securities financing regulation across repo, sec lending, and TBA.

    Primary desks: Secured Lending, Agency Lending, Prime Brokerage.
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    def run(
        self,
        since_days: int = 30,
        include_scan: bool = True,
    ) -> dict[str, Any]:
        """Full securities financing monitoring cycle.

        Returns:
            {sf_analyses, haircut_changes, collateral_changes,
             margin_changes, desk_actions, audit_summary}
        """
        if include_scan:
            self._scan(SF_DOMAINS, since_days)

        analyses = self._analyze_sf_filings()

        return {
            "sf_analyses": analyses,
            "haircut_changes": _extract_haircut_changes(analyses),
            "collateral_changes": _extract_field(analyses, "collateral_eligibility_changes"),
            "margin_changes": _extract_field(analyses, "margin_requirement_changes"),
            "desk_actions": _dedup_actions(analyses, "desk_action_items"),
            "rehypothecation_impacts": [a.get("rehypothecation_impact") for a in analyses if a.get("rehypothecation_impact") not in (None, "none")],
            "audit_summary": self.runtime.audit.summary(),
        }

    def collateral_schedule_updates(self) -> list[dict]:
        """Return all haircut and eligibility changes requiring collateral system updates."""
        analyses = self._analyze_sf_filings()
        updates = []
        for a in analyses:
            hc = a.get("haircut_changes", [])
            ce = a.get("collateral_eligibility_changes", [])
            if hc or ce:
                updates.append({
                    "filing_id": a.get("filing_id"),
                    "haircut_changes": hc,
                    "eligibility_changes": ce,
                })
        return updates

    def prime_brokerage_impacts(self) -> list[dict]:
        """Return changes directly affecting prime brokerage operations."""
        analyses = self._analyze_sf_filings()
        return [
            {"filing_id": a.get("filing_id"), "impacts": a.get("prime_brokerage_impacts", [])}
            for a in analyses if a.get("prime_brokerage_impacts")
        ]

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _scan(self, domains: list[str], since_days: int) -> dict:
        result = self.runtime.execute_skill("scan_cycle", {"domains": domains, "since_days": since_days})
        return result.data.get("stats", {}) if result.success else {}

    def _analyze_sf_filings(self) -> list[dict]:
        records = self.runtime.memory.get_filing_history(limit=50) if self.runtime.memory else []
        analyses = []
        for rec in records:
            filing = rec.content.get("filing", {})
            if filing.get("domain", "") not in SF_DOMAINS:
                continue
            result = self.runtime.execute_skill("securities_financing_analysis", {"filing": filing})
            if result.success:
                analyses.append(result.data)
        return analyses


def _extract_haircut_changes(analyses: list[dict]) -> list[dict]:
    changes = []
    for a in analyses:
        for hc in a.get("haircut_changes", []):
            changes.append({"filing_id": a.get("filing_id"), **hc})
    return changes


def _extract_field(analyses: list[dict], field: str) -> list:
    items = []
    for a in analyses:
        items.extend(a.get(field, []))
    return items


def _dedup_actions(analyses: list[dict], field: str) -> list[str]:
    seen: set[str] = set()
    actions: list[str] = []
    for a in analyses:
        for item in a.get(field, []):
            if item not in seen:
                seen.add(item)
                actions.append(item)
    return actions
