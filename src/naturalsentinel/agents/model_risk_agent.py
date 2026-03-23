"""ModelRiskAgent — SR 11-7 model governance and validation trigger monitoring.

Answers: "Which of our models need re-validation, new challengers, or
documentation updates based on recent regulatory guidance?"

Monitors Fed and OCC filings for model risk management guidance updates
and maps them to specific model types in the data science inventory —
optimization models, ML credit models, pricing models, stress testing models.
"""

from __future__ import annotations

from typing import Any

MODEL_RISK_DOMAINS = ["fed", "occ"]


class ModelRiskAgent:
    """
    Tracks SR 11-7 obligations and surfaces model validation triggers.

    Primary users: Lead Data Scientists, Model Risk Management, Quant teams.
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    def run(
        self,
        since_days: int = 30,
        model_inventory: list[str] | None = None,
        include_scan: bool = True,
    ) -> dict[str, Any]:
        """Full model risk monitoring cycle.

        Args:
            model_inventory: Optional list of model names/types to assess against.

        Returns:
            {model_risk_analyses, immediate_validations, governance_actions,
             examiner_gaps, audit_summary}
        """
        if include_scan:
            self._scan(MODEL_RISK_DOMAINS, since_days)

        analyses = self._analyze_model_risk_filings(model_inventory or [])

        return {
            "model_risk_analyses": analyses,
            "immediate_validations": _filter_by_urgency(analyses, "immediate"),
            "governance_actions": _extract_governance_actions(analyses),
            "examiner_gaps": _extract_examiner_gaps(analyses),
            "audit_summary": self.runtime.audit.summary(),
        }

    def models_requiring_revalidation(self, urgency: str = "immediate") -> list[str]:
        """Return model names that need re-validation at the specified urgency."""
        analyses = self._analyze_model_risk_filings([])
        models: list[str] = []
        for a in analyses:
            if a.get("urgency") == urgency or urgency == "all":
                models.extend(a.get("models_requiring_revalidation", []))
        return list(dict.fromkeys(models))  # deduplicate preserving order

    def challenger_required(self) -> list[str]:
        """Return model types where challenger models are now required."""
        analyses = self._analyze_model_risk_filings([])
        types: list[str] = []
        for a in analyses:
            if a.get("challenger_model_required"):
                types.extend(a.get("model_types_affected", []))
        return list(dict.fromkeys(types))

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _scan(self, domains: list[str], since_days: int) -> dict:
        result = self.runtime.execute_skill(
            "scan_cycle", {"domains": domains, "since_days": since_days}
        )
        return result.data.get("stats", {}) if result.success else {}

    def _analyze_model_risk_filings(self, model_inventory: list[str]) -> list[dict]:
        records = self.runtime.memory.get_filing_history(limit=50) if self.runtime.memory else []
        analyses = []
        for rec in records:
            filing = rec.content.get("filing", {})
            if filing.get("domain", "") not in MODEL_RISK_DOMAINS:
                continue
            result = self.runtime.execute_skill(
                "model_risk_assessment",
                {
                    "filing": filing,
                    "model_inventory": model_inventory,
                },
            )
            if result.success:
                analyses.append(result.data)
        return analyses


def _filter_by_urgency(analyses: list[dict], urgency: str) -> list[dict]:
    return [a for a in analyses if a.get("urgency") == urgency]


def _extract_governance_actions(analyses: list[dict]) -> list[str]:
    seen: set[str] = set()
    actions: list[str] = []
    for a in analyses:
        for action in a.get("governance_actions", []):
            if action not in seen:
                seen.add(action)
                actions.append(action)
    return actions


def _extract_examiner_gaps(analyses: list[dict]) -> list[str]:
    seen: set[str] = set()
    gaps: list[str] = []
    for a in analyses:
        for gap in a.get("examiner_readiness_gaps", []):
            if gap not in seen:
                seen.add(gap)
                gaps.append(gap)
    return gaps
