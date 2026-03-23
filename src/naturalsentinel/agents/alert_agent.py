"""AlertAgent — severity-based regulatory alerting orchestrator.

This agent answers the question: "What's on fire right now?"

It composes three skills into an alert-oriented workflow:
  1. scan_cycle (optional) — run a fresh analysis if requested
  2. alert_threshold       — scan stored analyses for severity breaches
  3. trend_analysis        — detect escalating regulatory pressure

Usage:
    from naturalsentinel.agents import AlertAgent
    from naturalsentinel.providers import MockProvider
    from naturalsentinel.memory import MemoryStore
    from naturalsentinel.agent_framework import AgentRuntime
    from naturalsentinel.skills import ALL_SKILLS

    runtime = AgentRuntime(provider=MockProvider(), memory=MemoryStore())
    for skill in ALL_SKILLS:
        runtime.register_skill(skill)

    agent = AlertAgent(runtime)

    # Check for high+ severity alerts (no new scan)
    alerts = agent.check(threshold="high")

    # Full cycle: scan first, then alert
    report = agent.scan_and_alert(domains=["sec", "cfpb"], threshold="medium")
"""

from __future__ import annotations

from typing import Any


class AlertAgent:
    """
    Monitors regulatory analyses and raises structured alerts.

    Supports two primary modes:
      - check()          — query existing memory for threshold breaches
      - scan_and_alert() — run a full scan cycle then check for alerts
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    # ── Primary interfaces ────────────────────────────────────────────────────

    def check(
        self,
        threshold: str = "high",
        limit: int = 50,
        include_trends: bool = True,
    ) -> dict[str, Any]:
        """
        Check stored analyses for threshold breaches.

        Returns:
            {
                "alerts":            list[dict],
                "summary":           dict,
                "immediate_actions": list[str],
                "trends":            dict | None,
                "audit_summary":     dict,
            }
        """
        alert_data = self._run_alert_threshold(threshold, limit)
        trends = self._run_trends(limit=limit) if include_trends else None
        immediate = _extract_immediate_actions(alert_data.get("alerts", []))

        return {
            "alerts": alert_data.get("alerts", []),
            "summary": alert_data.get("summary", {}),
            "immediate_actions": immediate,
            "trends": trends,
            "audit_summary": self.runtime.audit.summary(),
        }

    def scan_and_alert(
        self,
        domains: list[str] | None = None,
        since_days: int = 30,
        threshold: str = "high",
        include_trends: bool = True,
    ) -> dict[str, Any]:
        """
        Run a fresh scan cycle then immediately check for alerts.

        Returns same shape as check() plus "scan_stats": dict.
        """
        scan_stats = self._run_scan(domains or [], since_days)
        result = self.check(threshold=threshold, include_trends=include_trends)
        result["scan_stats"] = scan_stats
        return result

    def critical_only(self) -> list[dict]:
        """Fast path — return only CRITICAL alerts from stored memory."""
        data = self._run_alert_threshold("critical", limit=100)
        return data.get("alerts", [])

    def domain_summary(self, threshold: str = "medium") -> dict[str, list[dict]]:
        """Return alerts grouped by regulatory domain."""
        data = self._run_alert_threshold(threshold, limit=200)
        by_domain: dict[str, list[dict]] = {}
        for alert in data.get("alerts", []):
            dom = alert.get("domain", "UNKNOWN")
            by_domain.setdefault(dom, []).append(alert)
        return by_domain

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _run_alert_threshold(self, threshold: str, limit: int) -> dict:
        result = self.runtime.execute_skill(
            "alert_threshold",
            {
                "threshold": threshold,
                "limit": limit,
            },
        )
        return result.data if result.success else {"alerts": [], "summary": {"error": result.error}}

    def _run_scan(self, domains: list[str], since_days: int) -> dict:
        result = self.runtime.execute_skill(
            "scan_cycle",
            {
                "domains": domains,
                "since_days": since_days,
            },
        )
        return result.data.get("stats", {}) if result.success else {"error": result.error}

    def _run_trends(self, limit: int = 50) -> dict | None:
        result = self.runtime.execute_skill(
            "trend_analysis",
            {
                "limit": limit,
                "include_narrative": True,
            },
        )
        return result.data if result.success else None


# ── Utilities ─────────────────────────────────────────────────────────────────


def _extract_immediate_actions(alerts: list[dict]) -> list[str]:
    """Deduplicate action items across all alerts, preserving insertion order."""
    seen: set[str] = set()
    actions: list[str] = []
    for alert in alerts:
        for item in alert.get("action_items", []):
            if item not in seen:
                seen.add(item)
                actions.append(item)
    return actions
