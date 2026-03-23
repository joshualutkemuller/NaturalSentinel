"""AIGovernanceAgent — AI regulatory monitoring orchestrator.

Answers: "What EU AI Act risk tier, FTC AI obligations, algorithmic
accountability requirements, and model validation triggers does this
filing create, and what compliance deadlines are approaching?"

Designed for responsible AI officers, AI product teams, and legal counsel
navigating EU AI Act obligations, FTC guidance on AI, and algorithmic
accountability requirements. Also surfaces SR 11-7 / OCC model validation
triggers for regulated entities.

Composes two specialist skills:
  1. ai_regulatory_impact       — EU AI Act / FTC AI obligations
  2. algorithmic_accountability — bias audit, explainability, impact assessment

Plus three supporting skills:
  3. model_risk_assessment — SR 11-7 / OCC model validation triggers
  4. regime_detection      — detect active AI governance regime
  5. compliance_deadline   — surface AI law compliance deadlines

Usage:
    from naturalsentinel.agents import AIGovernanceAgent
    from naturalsentinel.providers import MockProvider
    from naturalsentinel.memory import MemoryStore
    from naturalsentinel.agent_framework import AgentRuntime
    from naturalsentinel.skills import ALL_SKILLS

    runtime = AgentRuntime(provider=MockProvider(), memory=MemoryStore())
    for skill in ALL_SKILLS:
        runtime.register_skill(skill)

    agent = AIGovernanceAgent(runtime)

    # Full AI assessment against a filing dict
    report = agent.full_ai_assessment(filing=my_filing, memory_context="EU AI Act audit")

    # Targeted queries
    tier      = agent.risk_tier_check(filing=my_filing)
    acct      = agent.accountability_obligations(filing=my_filing)
    regime    = agent.ai_regime_state(window_days=90)
    deadlines = agent.upcoming_ai_deadlines(look_ahead_days=90)
"""

from __future__ import annotations

from typing import Any


class AIGovernanceAgent:
    """
    Orchestrates AI regulatory monitoring for responsible AI officers,
    AI product teams, and legal counsel.

    Supported workflows:
      - full_ai_assessment()          — ai_regulatory_impact + algorithmic_accountability
      - risk_tier_check()             — EU AI Act risk tier classification only
      - accountability_obligations()  — bias audit and explainability obligations only
      - ai_regime_state()             — active AI governance regime snapshot
      - upcoming_ai_deadlines()       — approaching AI law compliance deadlines
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    # ── Primary interfaces ────────────────────────────────────────────────────

    def full_ai_assessment(
        self,
        filing: dict,
        memory_context: str = "",
    ) -> dict[str, Any]:
        """Run ai_regulatory_impact and algorithmic_accountability against a filing.

        Args:
            filing:         Normalised filing dict (domain, text, metadata …).
            memory_context: Optional free-text context injected from memory
                            to enrich skill prompts.

        Returns:
            {
                "ai_regulatory_impact":       dict,
                "algorithmic_accountability": dict,
                "audit_summary":              dict,
            }
        """
        params = {"filing": filing, "memory_context": memory_context}

        regulatory_impact = self._run_ai_regulatory_impact(params)
        accountability = self._run_algorithmic_accountability(params)

        return {
            "ai_regulatory_impact": regulatory_impact,
            "algorithmic_accountability": accountability,
            "audit_summary": self.runtime.audit.summary(),
        }

    def risk_tier_check(self, filing: dict) -> dict[str, Any]:
        """Run ai_regulatory_impact skill only, surfacing risk_tier_classification.

        Returns EU AI Act risk tier classification and associated FTC AI
        obligations identified in the filing.
        """
        result = self.runtime.execute_skill(
            "ai_regulatory_impact",
            {"filing": filing, "memory_context": ""},
        )
        return result.data if result.success else {"error": result.error}

    def accountability_obligations(self, filing: dict) -> dict[str, Any]:
        """Run algorithmic_accountability skill only.

        Returns bias audit requirements, explainability obligations, and
        algorithmic impact assessment triggers identified in the filing.
        """
        result = self.runtime.execute_skill(
            "algorithmic_accountability",
            {"filing": filing, "memory_context": ""},
        )
        return result.data if result.success else {"error": result.error}

    def ai_regime_state(self, window_days: int = 90) -> dict[str, Any]:
        """Run regime_detection filtered to AI governance domains.

        Args:
            window_days: Look-back window for regime activity detection.

        Returns regime snapshot covering EU AI Act, FTC AI guidance,
        and national AI accountability frameworks active in the specified window.
        """
        result = self.runtime.execute_skill(
            "regime_detection",
            {
                "domain_filter": ["ai_governance", "algorithmic_accountability", "ftc_ai"],
                "window_days": window_days,
            },
        )
        return result.data if result.success else {"error": result.error}

    def upcoming_ai_deadlines(self, look_ahead_days: int = 90) -> dict[str, Any]:
        """Surface approaching AI law compliance deadlines.

        Args:
            look_ahead_days: Number of days ahead to scan for deadlines.

        Returns deadline list scoped to AI regulatory domains (EU AI Act
        phase-in dates, FTC guidance compliance windows, SR 11-7 validation
        cycles, and algorithmic accountability reporting requirements).
        """
        result = self.runtime.execute_skill(
            "compliance_deadline",
            {
                "domain_filter": ["ai_governance", "algorithmic_accountability", "model_risk"],
                "look_ahead_days": look_ahead_days,
            },
        )
        return result.data if result.success else {"error": result.error}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _run_ai_regulatory_impact(self, params: dict) -> dict:
        result = self.runtime.execute_skill("ai_regulatory_impact", params)
        return result.data if result.success else {"error": result.error}

    def _run_algorithmic_accountability(self, params: dict) -> dict:
        result = self.runtime.execute_skill("algorithmic_accountability", params)
        return result.data if result.success else {"error": result.error}
