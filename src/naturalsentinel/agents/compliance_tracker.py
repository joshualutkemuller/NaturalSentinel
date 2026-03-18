"""ComplianceTrackerAgent — deadline-centric regulatory compliance orchestrator.

This agent answers the question: "What do we need to do, by when?"

It orchestrates three skills in a deliberate sequence:
  1. compliance_deadline  — extracts and categorises deadlines from memory
  2. generate_briefing    — synthesises a deadline-focused narrative (optional)
  3. export_report        — renders a shareable artefact in the chosen format

Usage:
    from naturalsentinel.agents import ComplianceTrackerAgent
    from naturalsentinel.providers import MockProvider
    from naturalsentinel.memory import MemoryStore
    from naturalsentinel.agent_framework import AgentRuntime
    from naturalsentinel.skills import ALL_SKILLS

    runtime = AgentRuntime(provider=MockProvider(), memory=MemoryStore())
    for skill in ALL_SKILLS:
        runtime.register_skill(skill)

    agent = ComplianceTrackerAgent(runtime)
    result = agent.run(look_ahead_days=60, export_format="markdown")
    print(result["calendar"]["overdue"])
"""

from __future__ import annotations

from typing import Any


class ComplianceTrackerAgent:
    """
    Tracks compliance obligations surfaced from regulatory analyses.

    Attributes:
        runtime: The AgentRuntime that provides skill execution.
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    # ── Primary interface ─────────────────────────────────────────────────────

    def run(
        self,
        look_ahead_days: int = 30,
        domain_filter: str = "",
        export_format: str = "markdown",
        include_briefing: bool = True,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Execute a full compliance tracking cycle.

        Returns:
            {
                "calendar": {overdue, due_soon, upcoming, no_deadline, summary},
                "report":   {format, content, row_count},
                "briefing": str | None,
                "audit_summary": dict,
            }
        """
        calendar = self._get_calendar(look_ahead_days, domain_filter, limit)
        report = self._get_export(export_format, domain_filter, limit)
        briefing = self._get_briefing(include_briefing)

        return {
            "calendar": calendar,
            "report": report,
            "briefing": briefing,
            "audit_summary": self.runtime.audit.summary(),
        }

    def overdue(self, domain_filter: str = "", limit: int = 100) -> list[dict]:
        """Return only overdue compliance items — fast path for alerts."""
        calendar = self._get_calendar(
            look_ahead_days=1, domain_filter=domain_filter, limit=limit
        )
        return calendar.get("overdue", [])

    def due_soon(self, look_ahead_days: int = 30, domain_filter: str = "") -> list[dict]:
        """Return compliance items due within look_ahead_days."""
        calendar = self._get_calendar(
            look_ahead_days=look_ahead_days, domain_filter=domain_filter
        )
        return calendar.get("due_soon", [])

    def export(self, fmt: str = "markdown", domain_filter: str = "", limit: int = 25) -> str:
        """Render a compliance report in the specified format and return the content."""
        result = self.runtime.execute_skill("export_report", {
            "format": fmt,
            "domain_filter": domain_filter,
            "limit": limit,
            "min_severity": "low",
        })
        if result.success:
            return result.data.get("content", "")
        return f"[Export failed: {result.error}]"

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_calendar(self, look_ahead_days: int, domain_filter: str, limit: int = 100) -> dict:
        result = self.runtime.execute_skill("compliance_deadline", {
            "look_ahead_days": look_ahead_days,
            "domain_filter": domain_filter,
            "limit": limit,
        })
        if result.success:
            return result.data
        return {
            "overdue": [], "due_soon": [], "upcoming": [], "no_deadline": [],
            "summary": {"error": result.error},
        }

    def _get_export(self, fmt: str, domain_filter: str, limit: int) -> dict:
        result = self.runtime.execute_skill("export_report", {
            "format": fmt,
            "domain_filter": domain_filter,
            "limit": min(limit, 25),
            "min_severity": "low",
        })
        if result.success:
            return result.data
        return {"format": fmt, "content": f"[Export failed: {result.error}]", "row_count": 0}

    def _get_briefing(self, include: bool) -> str | None:
        if not include:
            return None
        result = self.runtime.execute_skill("generate_briefing", {
            "audience": "compliance team",
            "limit": 10,
        })
        if result.success:
            return result.data
        return f"[Briefing unavailable: {result.error}]"
