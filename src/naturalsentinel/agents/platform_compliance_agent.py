"""PlatformComplianceAgent — platform competition and content liability monitoring orchestrator.

Answers: "What DMA/DSA/FTC antitrust obligations, content-moderation liability
exposure, M&A review signals, and algorithmic-accountability requirements does
this filing create for our platform?"

Designed for digital platform operators, Big Tech regulatory affairs teams,
and M&A counsel who need a consolidated view of platform-specific obligations
across antitrust, content, and algorithmic dimensions.

Composes four specialist skills:
  1. platform_antitrust_impact    — DMA/DSA/FTC antitrust obligations
  2. content_moderation_liability — Section 230/DSA content liability
  3. tech_merger_review           — M&A antitrust signals
  4. algorithmic_accountability   — bias audit and transparency obligations

Plus one regime skill:
  5. regime_detection — detect active platform regulation regime

Usage:
    from naturalsentinel.agents import PlatformComplianceAgent
    from naturalsentinel.providers import MockProvider
    from naturalsentinel.memory import MemoryStore
    from naturalsentinel.agent_framework import AgentRuntime
    from naturalsentinel.skills import ALL_SKILLS

    runtime = AgentRuntime(provider=MockProvider(), memory=MemoryStore())
    for skill in ALL_SKILLS:
        runtime.register_skill(skill)

    agent = PlatformComplianceAgent(runtime)

    # Full assessment against a filing dict
    report = agent.full_assessment(filing=my_filing, memory_context="Q2 review")

    # Targeted scans
    antitrust = agent.antitrust_scan(filing=my_filing)
    content   = agent.content_liability_check(filing=my_filing)
    merger    = agent.merger_signals(filing=my_filing)
    regime    = agent.platform_regime_state(window_days=90)
"""

from __future__ import annotations

from typing import Any


class PlatformComplianceAgent:
    """
    Orchestrates platform competition and content liability monitoring.

    Primary users: digital platform operators, Big Tech regulatory affairs
    teams, and M&A counsel.

    Supported workflows:
      - full_assessment()          — all four specialist skills in one pass
      - antitrust_scan()           — DMA/DSA/FTC antitrust obligations only
      - content_liability_check()  — Section 230/DSA content liability only
      - merger_signals()           — M&A antitrust signals only
      - platform_regime_state()    — active platform regulation regime snapshot
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    # ── Primary interfaces ────────────────────────────────────────────────────

    def full_assessment(
        self,
        filing: dict,
        memory_context: str = "",
    ) -> dict[str, Any]:
        """Run all four specialist skills against a filing.

        Args:
            filing:         Normalised filing dict (domain, text, metadata …).
            memory_context: Optional free-text context injected from memory
                            to enrich skill prompts.

        Returns:
            {
                "antitrust":              dict,
                "content_liability":      dict,
                "merger_review":          dict,
                "algorithmic_accountability": dict,
                "audit_summary":          dict,
            }
        """
        params = {"filing": filing, "memory_context": memory_context}

        antitrust   = self._run_platform_antitrust(params)
        content_lib = self._run_content_moderation_liability(params)
        merger      = self._run_tech_merger_review(params)
        algo        = self._run_algorithmic_accountability(params)

        return {
            "antitrust": antitrust,
            "content_liability": content_lib,
            "merger_review": merger,
            "algorithmic_accountability": algo,
            "audit_summary": self.runtime.audit.summary(),
        }

    def antitrust_scan(self, filing: dict) -> dict[str, Any]:
        """Run platform_antitrust_impact skill only.

        Returns DMA/DSA/FTC antitrust obligation analysis for the filing.
        """
        result = self.runtime.execute_skill(
            "platform_antitrust_impact",
            {"filing": filing, "memory_context": ""},
        )
        return result.data if result.success else {"error": result.error}

    def content_liability_check(self, filing: dict) -> dict[str, Any]:
        """Run content_moderation_liability skill only.

        Returns Section 230 / DSA content liability exposure analysis.
        """
        result = self.runtime.execute_skill(
            "content_moderation_liability",
            {"filing": filing, "memory_context": ""},
        )
        return result.data if result.success else {"error": result.error}

    def merger_signals(self, filing: dict) -> dict[str, Any]:
        """Run tech_merger_review skill only.

        Returns M&A antitrust signals extracted from the filing.
        """
        result = self.runtime.execute_skill(
            "tech_merger_review",
            {"filing": filing, "memory_context": ""},
        )
        return result.data if result.success else {"error": result.error}

    def platform_regime_state(self, window_days: int = 90) -> dict[str, Any]:
        """Run regime_detection filtered to platform regulation domains.

        Args:
            window_days: Look-back window for regime activity detection.

        Returns regime snapshot covering DMA, DSA, FTC platform rules, and
        related national platform laws active in the specified window.
        """
        result = self.runtime.execute_skill(
            "regime_detection",
            {
                "domain_filter": ["platform", "antitrust", "content_moderation"],
                "window_days": window_days,
            },
        )
        return result.data if result.success else {"error": result.error}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _run_platform_antitrust(self, params: dict) -> dict:
        result = self.runtime.execute_skill("platform_antitrust_impact", params)
        return result.data if result.success else {"error": result.error}

    def _run_content_moderation_liability(self, params: dict) -> dict:
        result = self.runtime.execute_skill("content_moderation_liability", params)
        return result.data if result.success else {"error": result.error}

    def _run_tech_merger_review(self, params: dict) -> dict:
        result = self.runtime.execute_skill("tech_merger_review", params)
        return result.data if result.success else {"error": result.error}

    def _run_algorithmic_accountability(self, params: dict) -> dict:
        result = self.runtime.execute_skill("algorithmic_accountability", params)
        return result.data if result.success else {"error": result.error}
