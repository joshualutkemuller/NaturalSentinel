"""Skill: Alert Threshold — flag analyses that breach severity thresholds.

Scans stored memory for filings at or above a configurable severity level
and produces a prioritised alert report with clear action assignments.
Useful for real-time triage dashboards and Slack/webhook integrations.
"""

from __future__ import annotations

from naturalsentinel.agent_framework import (
    Skill, SkillMetadata, SkillParameter, SkillContext, SkillResult,
    Permission, LatencyClass,
)

# Severity rank used for comparisons (lower index = lower severity)
_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class AlertThresholdSkill(Skill):
    metadata = SkillMetadata(
        name="alert_threshold",
        description=(
            "Scan stored analyses and raise alerts for any filing whose "
            "severity meets or exceeds the configured threshold. "
            "Returns a structured alert report with prioritised items, "
            "affected business lines, and recommended urgency tiers "
            "(immediate / 48-hour / 7-day)."
        ),
        version="1.0.0",
        permissions=Permission.MEMORY_READ,
        latency=LatencyClass.FAST,
        parameters=[
            SkillParameter(
                "threshold",
                "str",
                "Minimum severity to alert on: 'low', 'medium', 'high', or 'critical'.",
                required=False,
                default="high",
            ),
            SkillParameter(
                "limit",
                "int",
                "Maximum number of recent analyses to inspect.",
                required=False,
                default=50,
            ),
        ],
        returns=(
            "dict — {alerts: list[dict], summary: dict} where each alert has "
            "filing_id, title, domain, severity, deadline, action_items, "
            "urgency_tier, and affected_business_lines."
        ),
        dependencies=[],
        cacheable=False,
        tags=["alert", "monitoring", "threshold", "read-only"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        if context.memory is None:
            return SkillResult(
                skill_name=self.metadata.name, success=False, data=None,
                error="Memory access denied — requires MEMORY_READ permission",
            )

        raw_threshold = context.params.get("threshold", "high").lower()
        limit = context.params.get("limit", 50)

        threshold_rank = _SEVERITY_RANK.get(raw_threshold, 2)

        records = context.memory.get_filing_history(limit=limit)
        if not records:
            return SkillResult(
                skill_name=self.metadata.name,
                success=True,
                data={"alerts": [], "summary": {"total_inspected": 0, "alerts_raised": 0, "threshold": raw_threshold}},
                metadata={"message": "No analyses in memory. Run a scan cycle first."},
            )

        alerts: list[dict] = []
        severity_counts: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}

        for rec in records:
            filing = rec.content.get("filing", {})
            impact = rec.content.get("impact", {})

            severity = (impact.get("severity") or "low").lower()
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

            if _SEVERITY_RANK.get(severity, 0) < threshold_rank:
                continue

            deadline = impact.get("compliance_deadline")
            urgency_tier = _classify_urgency(severity, deadline)

            alerts.append({
                "filing_id": filing.get("id", rec.key),
                "title": filing.get("title", "Unknown"),
                "domain": filing.get("domain", "unknown").upper(),
                "severity": severity,
                "deadline": deadline,
                "urgency_tier": urgency_tier,
                "action_items": impact.get("action_items", []),
                "affected_business_lines": impact.get("affected_business_lines", []),
                "confidence": impact.get("confidence", 0.0),
                "risk_summary": impact.get("risk_summary", ""),
            })

        # Sort: critical first, then high; within tier sort by deadline presence
        alerts.sort(key=lambda a: (
            -_SEVERITY_RANK.get(a["severity"], 0),
            a["deadline"] is None,
            a["deadline"] or "",
        ))

        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data={
                "alerts": alerts,
                "summary": {
                    "total_inspected": len(records),
                    "alerts_raised": len(alerts),
                    "threshold": raw_threshold,
                    "severity_distribution": severity_counts,
                    "urgency_breakdown": _count_urgency(alerts),
                },
            },
            metadata={"threshold": raw_threshold, "alert_count": len(alerts)},
        )


def _classify_urgency(severity: str, deadline: str | None) -> str:
    """Map severity + deadline to a human urgency tier."""
    if severity == "critical":
        return "immediate"
    if severity == "high":
        if deadline:
            return "48-hour"
        return "7-day"
    return "7-day"


def _count_urgency(alerts: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for a in alerts:
        tier = a.get("urgency_tier", "unknown")
        counts[tier] = counts.get(tier, 0) + 1
    return counts
