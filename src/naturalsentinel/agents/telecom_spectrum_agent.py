"""TelecomSpectrumAgent — FCC spectrum and telecom infrastructure monitoring orchestrator.

Answers: "What FCC spectrum licensing changes, telecom infrastructure security
obligations, cybersecurity compliance requirements, and high-severity alerts
does this filing create for our spectrum or network operations?"

Designed for spectrum management teams, network operators, and FCC regulatory
affairs staff who need a consolidated view of spectrum policy, supply chain
security, and telecom-specific cybersecurity obligations.

Composes two specialist skills:
  1. spectrum_licensing_change      — FCC spectrum and auction analysis
  2. telecom_infrastructure_security — supply chain and network security

Plus three supporting skills:
  3. cybersecurity_compliance — FCC telecom cyber rules
  4. regime_detection         — detect active spectrum/telecom regime
  5. alert_threshold          — surface high-severity telecom alerts

Usage:
    from naturalsentinel.agents import TelecomSpectrumAgent
    from naturalsentinel.providers import MockProvider
    from naturalsentinel.memory import MemoryStore
    from naturalsentinel.agent_framework import AgentRuntime
    from naturalsentinel.skills import ALL_SKILLS

    runtime = AgentRuntime(provider=MockProvider(), memory=MemoryStore())
    for skill in ALL_SKILLS:
        runtime.register_skill(skill)

    agent = TelecomSpectrumAgent(runtime)

    # Full telecom scan against a filing dict
    report = agent.full_telecom_scan(filing=my_filing, memory_context="Q3 spectrum review")

    # Targeted queries
    spectrum = agent.spectrum_impact(filing=my_filing)
    infra    = agent.infrastructure_security_check(filing=my_filing)
    alerts   = agent.active_alerts(threshold="high")
    regime   = agent.telecom_regime_state(window_days=90)
"""

from __future__ import annotations

from typing import Any


class TelecomSpectrumAgent:
    """
    Orchestrates FCC spectrum and telecom infrastructure monitoring.

    Primary users: spectrum management teams, network operators, and
    FCC regulatory affairs staff.

    Supported workflows:
      - full_telecom_scan()              — spectrum + infrastructure skills in one pass
      - spectrum_impact()               — FCC spectrum and auction analysis only
      - infrastructure_security_check() — supply chain and network security only
      - active_alerts()                 — high-severity telecom alert surface
      - telecom_regime_state()          — active spectrum/telecom regime snapshot
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    # ── Primary interfaces ────────────────────────────────────────────────────

    def full_telecom_scan(
        self,
        filing: dict,
        memory_context: str = "",
    ) -> dict[str, Any]:
        """Run spectrum_licensing_change and telecom_infrastructure_security against a filing.

        Args:
            filing:         Normalised filing dict (domain, text, metadata …).
            memory_context: Optional free-text context injected from memory
                            to enrich skill prompts.

        Returns:
            {
                "spectrum_licensing":           dict,
                "infrastructure_security":      dict,
                "audit_summary":                dict,
            }
        """
        params = {"filing": filing, "memory_context": memory_context}

        spectrum = self._run_spectrum_licensing_change(params)
        infra = self._run_telecom_infrastructure_security(params)

        return {
            "spectrum_licensing": spectrum,
            "infrastructure_security": infra,
            "audit_summary": self.runtime.audit.summary(),
        }

    def spectrum_impact(self, filing: dict) -> dict[str, Any]:
        """Run spectrum_licensing_change skill only.

        Returns FCC spectrum licensing changes, auction obligations, and
        band-plan impacts identified in the filing.
        """
        result = self.runtime.execute_skill(
            "spectrum_licensing_change",
            {"filing": filing, "memory_context": ""},
        )
        return result.data if result.success else {"error": result.error}

    def infrastructure_security_check(self, filing: dict) -> dict[str, Any]:
        """Run telecom_infrastructure_security skill only.

        Returns supply chain security requirements and network infrastructure
        obligations identified in the filing.
        """
        result = self.runtime.execute_skill(
            "telecom_infrastructure_security",
            {"filing": filing, "memory_context": ""},
        )
        return result.data if result.success else {"error": result.error}

    def active_alerts(self, threshold: str = "high") -> dict[str, Any]:
        """Surface telecom-domain alerts at or above the specified severity threshold.

        Args:
            threshold: Severity floor for returned alerts ("low", "medium",
                       "high", or "critical").

        Returns alert list scoped to spectrum and telecom regulatory domains
        at or above the requested severity level.
        """
        result = self.runtime.execute_skill(
            "alert_threshold",
            {
                "threshold": threshold,
                "domain_filter": [
                    "spectrum",
                    "telecom",
                    "fcc",
                    "infrastructure_security",
                ],
            },
        )
        return result.data if result.success else {"error": result.error}

    def telecom_regime_state(self, window_days: int = 90) -> dict[str, Any]:
        """Run regime_detection filtered to spectrum and telecom domains.

        Args:
            window_days: Look-back window for regime activity detection.

        Returns regime snapshot covering FCC spectrum rules, telecom
        infrastructure security mandates, and related cybersecurity
        frameworks active in the specified window.
        """
        result = self.runtime.execute_skill(
            "regime_detection",
            {
                "domain_filter": [
                    "spectrum",
                    "telecom",
                    "fcc",
                    "infrastructure_security",
                ],
                "window_days": window_days,
            },
        )
        return result.data if result.success else {"error": result.error}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _run_spectrum_licensing_change(self, params: dict) -> dict:
        result = self.runtime.execute_skill("spectrum_licensing_change", params)
        return result.data if result.success else {"error": result.error}

    def _run_telecom_infrastructure_security(self, params: dict) -> dict:
        result = self.runtime.execute_skill("telecom_infrastructure_security", params)
        return result.data if result.success else {"error": result.error}
