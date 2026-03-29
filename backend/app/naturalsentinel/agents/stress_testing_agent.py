"""StressTestingAgent — CCAR/DFAST scenario monitoring and desk P&L mapping.

Answers: "What are the new stress scenarios, how do they differ from last year,
and what's the estimated P&L impact on each desk?"

Monitors Fed filings for CCAR/DFAST scenario releases, exploratory shocks,
and stress testing methodology updates. Parses macro variable paths and maps
them to desk-level P&L drivers — directly actionable for stress testing teams,
capital planning, and the repo/securities financing desks (the exploratory
repo shock scenario is particularly relevant).
"""

from __future__ import annotations

from typing import Any

STRESS_DOMAINS = ["fed"]


class StressTestingAgent:
    """
    Extracts stress test scenarios and maps them to desk P&L impacts.

    Primary users: Stress Testing Team, Capital Planning, Risk Management.
    Primary desks: All desks subject to CCAR — Repo, Prime, Secured, Agency.
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    def run(
        self,
        since_days: int = 90,
        include_scan: bool = True,
    ) -> dict[str, Any]:
        """Full stress testing monitoring cycle.

        Returns:
            {scenario_analyses, macro_variables, sf_stresses,
             desk_pl_drivers, submission_deadlines, model_updates,
             capital_adequacy_impacts, audit_summary}
        """
        if include_scan:
            self._scan(STRESS_DOMAINS, since_days)

        analyses = self._analyze_stress_filings()

        return {
            "scenario_analyses": analyses,
            "macro_variables": _extract_field(analyses, "macro_variables"),
            "sf_stresses": _extract_field(analyses, "securities_financing_stress"),
            "desk_pl_drivers": _extract_field(analyses, "desk_pl_drivers"),
            "submission_deadlines": [
                {
                    "filing_id": a.get("filing_id"),
                    "deadline": a.get("submission_deadline"),
                }
                for a in analyses
                if a.get("submission_deadline")
            ],
            "model_update_requirements": _extract_field(
                analyses, "model_update_requirements"
            ),
            "capital_adequacy_impacts": _extract_field(
                analyses, "capital_adequacy_impacts"
            ),
            "hedging_implications": _extract_field(analyses, "hedging_implications"),
            "audit_summary": self.runtime.audit.summary(),
        }

    def repo_specific_stress(self) -> list[dict]:
        """Return stress variables specifically affecting the repo/sec financing book."""
        analyses = self._analyze_stress_filings()
        repo_stresses = []
        for a in analyses:
            for stress in a.get("securities_financing_stress", []):
                if any(
                    kw in str(stress).lower()
                    for kw in ["repo", "financing", "collateral", "margin"]
                ):
                    repo_stresses.append(
                        {
                            "filing_id": a.get("filing_id"),
                            "scenario_type": a.get("scenario_type"),
                            **stress,
                        }
                    )
        return repo_stresses

    def nearest_submission_deadline(self) -> str | None:
        """Return the soonest CCAR/DFAST submission deadline found."""
        analyses = self._analyze_stress_filings()
        deadlines = [
            a["submission_deadline"] for a in analyses if a.get("submission_deadline")
        ]
        return min(deadlines) if deadlines else None

    def desk_impacts_by_desk(self, desk_name: str) -> list[dict]:
        """Return P&L drivers for a specific desk (case-insensitive substring match)."""
        analyses = self._analyze_stress_filings()
        impacts = []
        for a in analyses:
            for driver in a.get("desk_pl_drivers", []):
                if desk_name.lower() in str(driver.get("desk", "")).lower():
                    impacts.append({"filing_id": a.get("filing_id"), **driver})
        return impacts

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _scan(self, domains: list[str], since_days: int) -> dict:
        result = self.runtime.execute_skill(
            "scan_cycle", {"domains": domains, "since_days": since_days}
        )
        return result.data.get("stats", {}) if result.success else {}

    def _analyze_stress_filings(self) -> list[dict]:
        records = (
            self.runtime.memory.get_filing_history(limit=50)
            if self.runtime.memory
            else []
        )
        analyses = []
        for rec in records:
            filing = rec.content.get("filing", {})
            if filing.get("domain", "") not in STRESS_DOMAINS:
                continue
            result = self.runtime.execute_skill(
                "stress_testing_signal", {"filing": filing}
            )
            if result.success and result.data.get("macro_variables"):
                analyses.append(result.data)
        return analyses


def _extract_field(analyses: list[dict], field: str) -> list:
    items = []
    for a in analyses:
        items.extend(a.get(field, []))
    return items
