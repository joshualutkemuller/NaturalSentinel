"""AgencyMortgageAgent — FHFA, GSE, and agency MBS regulatory monitoring.

Answers: "What changed at Fannie, Freddie, or FHFA, and how does it affect
our Agency Lending book, TBA trading, collateral haircuts, and prepay models?"

Dedicated to the Agency Lending desk — monitors FHFA directives,
Fannie/Freddie selling guide updates, conforming limit changes, g-fee
adjustments, and CRT program rules.
"""

from __future__ import annotations

from typing import Any

AGENCY_DOMAINS = ["fhfa"]
SECONDARY_DOMAINS = ["fed", "sec"]  # For MBS-related rule changes


class AgencyMortgageAgent:
    """
    Monitors agency MBS regulatory environment for the Agency Lending desk.

    Primary desks: Agency Lending, Agency MBS / TBA Trading, GSE Collateral.
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    def run(
        self,
        since_days: int = 30,
        include_scan: bool = True,
    ) -> dict[str, Any]:
        """Full agency mortgage monitoring cycle.

        Returns:
            {agency_analyses, conforming_limit_changes, haircut_updates,
             gfee_adjustments, tba_eligibility_changes, prepay_model_impacts,
             desk_actions, audit_summary}
        """
        if include_scan:
            self._scan(AGENCY_DOMAINS + SECONDARY_DOMAINS, since_days)

        analyses = self._analyze_agency_filings()

        return {
            "agency_analyses": analyses,
            "conforming_limit_changes": [
                a.get("conforming_limit_changes", {})
                for a in analyses
                if a.get("conforming_limit_changes")
            ],
            "haircut_updates": _extract_field(analyses, "collateral_haircut_updates"),
            "gfee_adjustments": _extract_field(analyses, "gfee_adjustments"),
            "tba_eligibility_changes": _extract_field(
                analyses, "tba_eligibility_changes"
            ),
            "prepay_model_impacts": _extract_field(
                analyses, "prepayment_model_implications"
            ),
            "desk_actions": _dedup(analyses, "desk_action_items"),
            "audit_summary": self.runtime.audit.summary(),
        }

    def collateral_system_updates_required(self) -> bool:
        """Return True if any analysis requires collateral system updates."""
        analyses = self._analyze_agency_filings()
        return any(a.get("collateral_haircut_updates") for a in analyses)

    def conforming_limit_summary(self) -> dict:
        """Return the most recent conforming limit change."""
        analyses = self._analyze_agency_filings()
        for a in analyses:
            limits = a.get("conforming_limit_changes")
            if limits:
                return limits
        return {}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _scan(self, domains: list[str], since_days: int) -> dict:
        result = self.runtime.execute_skill(
            "scan_cycle", {"domains": domains, "since_days": since_days}
        )
        return result.data.get("stats", {}) if result.success else {}

    def _analyze_agency_filings(self) -> list[dict]:
        records = (
            self.runtime.memory.get_filing_history(limit=50)
            if self.runtime.memory
            else []
        )
        analyses = []
        for rec in records:
            filing = rec.content.get("filing", {})
            if filing.get("domain", "") not in AGENCY_DOMAINS:
                continue
            result = self.runtime.execute_skill(
                "agency_mortgage_analysis", {"filing": filing}
            )
            if result.success:
                analyses.append(result.data)
        return analyses


def _extract_field(analyses: list[dict], field: str) -> list:
    items = []
    for a in analyses:
        items.extend(a.get(field, []))
    return items


def _dedup(analyses: list[dict], field: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for a in analyses:
        for item in a.get(field, []):
            if item not in seen:
                seen.add(item)
                result.append(item)
    return result
