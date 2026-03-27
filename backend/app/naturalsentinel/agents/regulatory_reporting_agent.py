"""RegulatoryReportingAgent — reporting obligation and pipeline change monitoring.

Answers: "Do we have a new reporting requirement, did a form schema change,
or did a submission deadline shift — and what data pipeline work is needed?"

Monitors all domains for changes to CCAR/DFAST, Form PF, FR Y-14, FINRA
reporting, and SFTR — giving data engineering teams early warning before
a schema or methodology change breaks a production pipeline.
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


class RegulatoryReportingAgent:
    """
    Monitors all regulatory domains for reporting obligation changes.

    Primary users: Data Engineering, Compliance Reporting, Risk Operations.
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    def run(
        self,
        since_days: int = 30,
        include_scan: bool = True,
        domains: list[str] | None = None,
    ) -> dict[str, Any]:
        """Full reporting obligation monitoring cycle.

        Returns:
            {reporting_analyses, new_obligations, schema_changes,
             deadline_changes, high_effort_items, pipeline_impacts,
             audit_summary}
        """
        target_domains = domains or ALL_DOMAINS
        if include_scan:
            self._scan(target_domains, since_days)

        analyses = self._analyze_reporting_filings(target_domains)

        return {
            "reporting_analyses": analyses,
            "new_obligations": _extract_field(analyses, "new_reporting_obligations"),
            "schema_changes": _extract_field(analyses, "schema_changes"),
            "deadline_changes": _extract_field(analyses, "deadline_changes"),
            "high_effort_items": [
                a for a in analyses if a.get("estimated_build_effort") == "high"
            ],
            "pipeline_impacts": _extract_field(analyses, "system_pipeline_impacts"),
            "methodology_updates": _extract_field(analyses, "methodology_updates"),
            "audit_summary": self.runtime.audit.summary(),
        }

    def upcoming_deadlines(self) -> list[dict]:
        """Return all reporting deadline changes sorted by proximity."""
        analyses = self._analyze_reporting_filings(ALL_DOMAINS)
        deadlines = []
        for a in analyses:
            for d in a.get("deadline_changes", []):
                deadlines.append({"filing_id": a.get("filing_id"), **d})
        return sorted(deadlines, key=lambda x: x.get("new_deadline") or "9999")

    def build_backlog(self) -> list[dict]:
        """Return all system pipeline impacts as a prioritised build backlog."""
        analyses = self._analyze_reporting_filings(ALL_DOMAINS)
        backlog = []
        effort_rank = {"high": 3, "medium": 2, "low": 1}
        for a in analyses:
            for impact in a.get("system_pipeline_impacts", []):
                backlog.append(
                    {
                        "filing_id": a.get("filing_id"),
                        "domain": a.get("domain"),
                        "impact": impact,
                        "effort": a.get("estimated_build_effort", "low"),
                    }
                )
        return sorted(backlog, key=lambda x: -effort_rank.get(x["effort"], 0))

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _scan(self, domains: list[str], since_days: int) -> dict:
        result = self.runtime.execute_skill(
            "scan_cycle", {"domains": domains, "since_days": since_days}
        )
        return result.data.get("stats", {}) if result.success else {}

    def _analyze_reporting_filings(self, domains: list[str]) -> list[dict]:
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
                "regulatory_reporting_analysis", {"filing": filing}
            )
            if result.success and (
                result.data.get("new_reporting_obligations")
                or result.data.get("schema_changes")
                or result.data.get("deadline_changes")
            ):
                analyses.append(result.data)
        return analyses


def _extract_field(analyses: list[dict], field: str) -> list:
    items = []
    for a in analyses:
        items.extend(a.get(field, []))
    return items
