"""DataPrivacyAgent — data privacy and cross-border data transfer monitoring orchestrator.

Answers: "What GDPR/CCPA/state privacy obligations, data localisation rules,
and cross-border transfer restrictions does this filing impose, and what
compliance deadlines are approaching?"

Designed for Data Protection Officers (DPOs), privacy engineering teams,
and international compliance counsel who need a consolidated view of
privacy obligations and transfer restrictions across jurisdictions.

Composes two specialist skills:
  1. data_privacy_obligation   — GDPR/CCPA/state privacy obligations
  2. data_residency_obligation — localisation and cross-border transfer rules

Plus two utility skills:
  3. regime_detection    — detect active data privacy regime
  4. compliance_deadline — surface privacy law compliance deadlines

Usage:
    from naturalsentinel.agents import DataPrivacyAgent
    from naturalsentinel.providers import MockProvider
    from naturalsentinel.memory import MemoryStore
    from naturalsentinel.agent_framework import AgentRuntime
    from naturalsentinel.skills import ALL_SKILLS

    runtime = AgentRuntime(provider=MockProvider(), memory=MemoryStore())
    for skill in ALL_SKILLS:
        runtime.register_skill(skill)

    agent = DataPrivacyAgent(runtime)

    # Full privacy scan against a filing dict
    report = agent.full_privacy_scan(filing=my_filing, memory_context="GDPR audit")

    # Targeted queries
    obligations = agent.privacy_obligations(filing=my_filing)
    transfers   = agent.transfer_impact(filing=my_filing)
    deadlines   = agent.upcoming_deadlines(look_ahead_days=60)
    regime      = agent.privacy_regime_state(window_days=90)
"""

from __future__ import annotations

from typing import Any


class DataPrivacyAgent:
    """
    Orchestrates data privacy and cross-border data transfer monitoring.

    Primary users: DPOs, privacy engineering teams, and international
    compliance counsel.

    Supported workflows:
      - full_privacy_scan()     — both specialist skills in one pass
      - privacy_obligations()   — GDPR/CCPA/state obligations only
      - transfer_impact()       — localisation and transfer restriction only
      - upcoming_deadlines()    — approaching privacy compliance deadlines
      - privacy_regime_state()  — active privacy regulation regime snapshot
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    # ── Primary interfaces ────────────────────────────────────────────────────

    def full_privacy_scan(
        self,
        filing: dict,
        memory_context: str = "",
    ) -> dict[str, Any]:
        """Run both specialist privacy skills against a filing.

        Args:
            filing:         Normalised filing dict (domain, text, metadata …).
            memory_context: Optional free-text context injected from memory
                            to enrich skill prompts.

        Returns:
            {
                "privacy_obligations":      dict,
                "transfer_restrictions":    dict,
                "audit_summary":            dict,
            }
        """
        params = {"filing": filing, "memory_context": memory_context}

        obligations  = self._run_data_privacy_obligation(params)
        transfers    = self._run_data_residency_obligation(params)

        return {
            "privacy_obligations": obligations,
            "transfer_restrictions": transfers,
            "audit_summary": self.runtime.audit.summary(),
        }

    def privacy_obligations(self, filing: dict) -> dict[str, Any]:
        """Run data_privacy_obligation skill only.

        Returns GDPR, CCPA, and applicable state privacy law obligations
        extracted from the filing.
        """
        result = self.runtime.execute_skill(
            "data_privacy_obligation",
            {"filing": filing, "memory_context": ""},
        )
        return result.data if result.success else {"error": result.error}

    def transfer_impact(self, filing: dict) -> dict[str, Any]:
        """Run data_residency_obligation skill only.

        Returns localisation requirements and cross-border transfer
        restrictions identified in the filing.
        """
        result = self.runtime.execute_skill(
            "data_residency_obligation",
            {"filing": filing, "memory_context": ""},
        )
        return result.data if result.success else {"error": result.error}

    def upcoming_deadlines(self, look_ahead_days: int = 60) -> dict[str, Any]:
        """Surface approaching privacy law compliance deadlines.

        Args:
            look_ahead_days: Number of days ahead to scan for deadlines.

        Returns deadline list scoped to data privacy regulatory domains
        (GDPR, CCPA, state privacy laws, and cross-border transfer frameworks).
        """
        result = self.runtime.execute_skill(
            "compliance_deadline",
            {
                "domain_filter": ["privacy", "data_residency", "gdpr", "ccpa"],
                "look_ahead_days": look_ahead_days,
            },
        )
        return result.data if result.success else {"error": result.error}

    def privacy_regime_state(self, window_days: int = 90) -> dict[str, Any]:
        """Run regime_detection filtered to data privacy domains.

        Args:
            window_days: Look-back window for regime activity detection.

        Returns regime snapshot covering GDPR, CCPA, state privacy laws,
        and international data transfer frameworks active in the specified window.
        """
        result = self.runtime.execute_skill(
            "regime_detection",
            {
                "domain_filter": ["privacy", "data_residency", "gdpr", "ccpa"],
                "window_days": window_days,
            },
        )
        return result.data if result.success else {"error": result.error}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _run_data_privacy_obligation(self, params: dict) -> dict:
        result = self.runtime.execute_skill("data_privacy_obligation", params)
        return result.data if result.success else {"error": result.error}

    def _run_data_residency_obligation(self, params: dict) -> dict:
        result = self.runtime.execute_skill("data_residency_obligation", params)
        return result.data if result.success else {"error": result.error}
