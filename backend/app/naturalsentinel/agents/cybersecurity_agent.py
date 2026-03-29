"""CybersecurityAgent — cybersecurity regulatory monitoring orchestrator.

Answers: "What CISA directive obligations, FCC telecom cyber rules, SEC cyber
disclosure requirements, data sovereignty constraints, and critical infrastructure
security mandates does this filing impose, and what patch or disclosure deadlines
are approaching?"

Designed for CISOs, security compliance officers, and critical infrastructure
operators who need a consolidated view of cybersecurity obligations across
federal directives, sector-specific rules, and cross-border data residency
implications.

Composes three specialist skills:
  1. cybersecurity_compliance       — CISA/FCC/SEC cyber obligations
  2. data_residency_obligation      — data sovereignty and localisation rules
  3. telecom_infrastructure_security — network security infrastructure

Plus two supporting skills:
  4. alert_threshold     — surface critical cybersecurity alerts
  5. compliance_deadline — patch and disclosure deadlines

Usage:
    from app.naturalsentinel.agents import CybersecurityAgent
    from app.naturalsentinel.providers import MockProvider
    from app.naturalsentinel.memory import MemoryStore
    from app.naturalsentinel.agent_framework import AgentRuntime
    from app.naturalsentinel.skills import ALL_SKILLS

    runtime = AgentRuntime(provider=MockProvider(), memory=MemoryStore())
    for skill in ALL_SKILLS:
        runtime.register_skill(skill)

    agent = CybersecurityAgent(runtime)

    # Full cyber scan against a filing dict
    report = agent.full_cyber_scan(filing=my_filing, memory_context="CISA audit cycle")

    # Targeted queries
    incident  = agent.incident_reporting_impact(filing=my_filing)
    alerts    = agent.critical_alerts()
    deadlines = agent.patch_deadlines(look_ahead_days=14)
    supply    = agent.supply_chain_check(filing=my_filing)
"""

from __future__ import annotations

from typing import Any


class CybersecurityAgent:
    """
    Orchestrates cybersecurity regulatory monitoring for CISOs, security
    compliance officers, and critical infrastructure operators.

    Supported workflows:
      - full_cyber_scan()              — cybersecurity_compliance + data_residency
                                        + telecom_infrastructure in one pass
      - incident_reporting_impact()   — cybersecurity_compliance focused on
                                        incident reporting obligations only
      - critical_alerts()             — surface CRITICAL-severity cyber alerts
      - patch_deadlines()             — approaching patch and disclosure deadlines
      - supply_chain_check()          — telecom infrastructure supply chain only
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    # ── Primary interfaces ────────────────────────────────────────────────────

    def full_cyber_scan(
        self,
        filing: dict,
        memory_context: str = "",
    ) -> dict[str, Any]:
        """Run cybersecurity_compliance, data_residency_obligation, and
        telecom_infrastructure_security against a filing.

        Args:
            filing:         Normalised filing dict (domain, text, metadata …).
            memory_context: Optional free-text context injected from memory
                            to enrich skill prompts.

        Returns:
            {
                "cybersecurity_compliance":        dict,
                "data_residency":                  dict,
                "infrastructure_security":         dict,
                "audit_summary":                   dict,
            }
        """
        params = {"filing": filing, "memory_context": memory_context}

        cyber_compliance = self._run_cybersecurity_compliance(params)
        data_residency = self._run_data_residency_obligation(params)
        infra_security = self._run_telecom_infrastructure_security(params)

        return {
            "cybersecurity_compliance": cyber_compliance,
            "data_residency": data_residency,
            "infrastructure_security": infra_security,
            "audit_summary": self.runtime.audit.summary(),
        }

    def incident_reporting_impact(self, filing: dict) -> dict[str, Any]:
        """Run cybersecurity_compliance skill focused on incident reporting fields.

        Returns CISA, FCC, and SEC cyber incident reporting obligations,
        notification timelines, and disclosure requirements identified
        in the filing.
        """
        result = self.runtime.execute_skill(
            "cybersecurity_compliance",
            {"filing": filing, "memory_context": "incident_reporting"},
        )
        return result.data if result.success else {"error": result.error}

    def critical_alerts(self) -> list[dict]:
        """Surface CRITICAL-severity cybersecurity alerts from stored memory.

        Returns a list of critical alert dicts scoped to cybersecurity
        and critical infrastructure regulatory domains.
        """
        result = self.runtime.execute_skill(
            "alert_threshold",
            {
                "threshold": "critical",
                "domain_filter": ["cybersecurity", "cisa", "fcc_cyber", "sec_cyber"],
            },
        )
        if result.success:
            return result.data.get("alerts", [])
        return [{"error": result.error}]

    def patch_deadlines(self, look_ahead_days: int = 14) -> dict[str, Any]:
        """Surface approaching patch and disclosure compliance deadlines.

        Args:
            look_ahead_days: Number of days ahead to scan for deadlines.
                             Defaults to 14 to capture imminent CISA KEV
                             patch windows and SEC disclosure timelines.

        Returns deadline list scoped to cybersecurity domains including
        CISA Known Exploited Vulnerabilities catalogue patch dates, SEC
        four-day incident disclosure windows, and FCC breach notification
        requirements.
        """
        result = self.runtime.execute_skill(
            "compliance_deadline",
            {
                "domain_filter": ["cybersecurity", "cisa", "fcc_cyber", "sec_cyber"],
                "look_ahead_days": look_ahead_days,
            },
        )
        return result.data if result.success else {"error": result.error}

    def supply_chain_check(self, filing: dict) -> dict[str, Any]:
        """Run telecom_infrastructure_security skill only.

        Returns supply chain security obligations and network infrastructure
        security requirements identified in the filing, covering FCC Huawei/ZTE
        restrictions, NTIA SBOM mandates, and related federal supply chain rules.
        """
        result = self.runtime.execute_skill(
            "telecom_infrastructure_security",
            {"filing": filing, "memory_context": ""},
        )
        return result.data if result.success else {"error": result.error}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _run_cybersecurity_compliance(self, params: dict) -> dict:
        result = self.runtime.execute_skill("cybersecurity_compliance", params)
        return result.data if result.success else {"error": result.error}

    def _run_data_residency_obligation(self, params: dict) -> dict:
        result = self.runtime.execute_skill("data_residency_obligation", params)
        return result.data if result.success else {"error": result.error}

    def _run_telecom_infrastructure_security(self, params: dict) -> dict:
        result = self.runtime.execute_skill("telecom_infrastructure_security", params)
        return result.data if result.success else {"error": result.error}
