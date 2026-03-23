"""Skill: Compliance Deadline Tracker — extract and prioritise deadlines.

Pulls compliance_deadline fields from stored analyses, computes days-until
relative to today, and returns a calendar-style list sorted by urgency.
Tracks overdue, due-soon (≤30 days), and future obligations.
"""

from __future__ import annotations

from datetime import UTC, datetime

from naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)

_DATE_FORMATS = ["%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"]


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _days_until(deadline: datetime) -> int:
    now = datetime.now(UTC)
    return (deadline - now).days


class ComplianceDeadlineSkill(Skill):
    metadata = SkillMetadata(
        name="compliance_deadline",
        description=(
            "Extract compliance deadlines from stored analyses and return a "
            "prioritised calendar view. Items are categorised as 'overdue', "
            "'due_soon' (within look-ahead window), or 'upcoming'. "
            "Useful for building compliance calendars, dashboards, and "
            "automated reminder workflows."
        ),
        version="1.0.0",
        permissions=Permission.MEMORY_READ,
        latency=LatencyClass.FAST,
        parameters=[
            SkillParameter(
                "look_ahead_days",
                "int",
                "Number of days to consider 'due soon' (default 30).",
                required=False,
                default=30,
            ),
            SkillParameter(
                "domain_filter",
                "str",
                "Limit to a single agency code (e.g. 'sec'). Empty = all domains.",
                required=False,
                default="",
            ),
            SkillParameter(
                "limit",
                "int",
                "Maximum number of recent analyses to scan.",
                required=False,
                default=100,
            ),
        ],
        returns=(
            "dict — {overdue: list, due_soon: list, upcoming: list, "
            "no_deadline: list, summary: dict} where each item has "
            "filing_id, title, domain, severity, deadline, days_until, "
            "action_items."
        ),
        dependencies=[],
        cacheable=False,
        tags=["deadline", "calendar", "compliance", "read-only"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        if context.memory is None:
            return SkillResult(
                skill_name=self.metadata.name,
                success=False,
                data=None,
                error="Memory access denied — requires MEMORY_READ permission",
            )

        look_ahead = context.params.get("look_ahead_days", 30)
        domain_filter = (context.params.get("domain_filter") or "").lower().strip()
        limit = context.params.get("limit", 100)

        records = context.memory.get_filing_history(
            domain=domain_filter or None,
            limit=limit,
        )

        overdue: list[dict] = []
        due_soon: list[dict] = []
        upcoming: list[dict] = []
        no_deadline: list[dict] = []

        for rec in records:
            filing = rec.content.get("filing", {})
            impact = rec.content.get("impact", {})

            if domain_filter and filing.get("domain", "").lower() != domain_filter:
                continue

            raw_deadline = impact.get("compliance_deadline")
            parsed = _parse_date(raw_deadline)

            item = {
                "filing_id": filing.get("id", rec.key),
                "title": filing.get("title", "Unknown"),
                "domain": filing.get("domain", "unknown").upper(),
                "severity": (impact.get("severity") or "unknown").lower(),
                "deadline": raw_deadline,
                "action_items": impact.get("action_items", []),
                "affected_business_lines": impact.get("affected_business_lines", []),
                "days_until": None,
            }

            if parsed is None:
                no_deadline.append(item)
                continue

            days = _days_until(parsed)
            item["days_until"] = days

            if days < 0:
                overdue.append(item)
            elif days <= look_ahead:
                due_soon.append(item)
            else:
                upcoming.append(item)

        # Sort each bucket by days_until ascending (most urgent first)
        _sort_by_days(overdue)
        _sort_by_days(due_soon)
        _sort_by_days(upcoming)

        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data={
                "overdue": overdue,
                "due_soon": due_soon,
                "upcoming": upcoming,
                "no_deadline": no_deadline,
                "summary": {
                    "total_analyzed": len(records),
                    "overdue_count": len(overdue),
                    "due_soon_count": len(due_soon),
                    "upcoming_count": len(upcoming),
                    "no_deadline_count": len(no_deadline),
                    "look_ahead_days": look_ahead,
                    "domain_filter": domain_filter or "all",
                },
            },
            metadata={"overdue": len(overdue), "due_soon": len(due_soon)},
        )


def _sort_by_days(items: list[dict]) -> None:
    items.sort(key=lambda x: (x["days_until"] is None, x["days_until"] or 0))
