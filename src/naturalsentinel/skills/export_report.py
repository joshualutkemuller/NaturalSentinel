"""Skill: Export Report — produce structured, shareable reports from analyses.

Reads stored analyses from memory and renders them as a chosen format:
  - 'markdown'  : A formatted compliance report ready for email / Confluence
  - 'json'      : Machine-readable structured output for downstream systems
  - 'csv'       : Flat tabular data suitable for Excel / BI tools

No LLM calls required — this is a pure-data formatting skill.
"""

from __future__ import annotations

import json
from datetime import UTC

from naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)

_VALID_FORMATS = {"markdown", "json", "csv"}


class ExportReportSkill(Skill):
    metadata = SkillMetadata(
        name="export_report",
        description=(
            "Generate a structured compliance report from stored analyses. "
            "Supports three output formats: 'markdown' (human-readable report), "
            "'json' (machine-readable structured export), and 'csv' (flat tabular "
            "data for spreadsheets/BI tools). No LLM calls — deterministic output."
        ),
        version="1.0.0",
        permissions=Permission.MEMORY_READ,
        latency=LatencyClass.FAST,
        parameters=[
            SkillParameter(
                "format",
                "str",
                "Output format: 'markdown', 'json', or 'csv'.",
                required=False,
                default="markdown",
            ),
            SkillParameter(
                "limit",
                "int",
                "Maximum number of recent analyses to include.",
                required=False,
                default=25,
            ),
            SkillParameter(
                "domain_filter",
                "str",
                "Limit to a single agency code (e.g. 'sec'). Empty = all.",
                required=False,
                default="",
            ),
            SkillParameter(
                "min_severity",
                "str",
                "Only include analyses at or above this severity (low/medium/high/critical).",
                required=False,
                default="low",
            ),
        ],
        returns="dict — {format: str, content: str, row_count: int, metadata: dict}",
        dependencies=[],
        cacheable=False,
        tags=["export", "reporting", "output", "read-only"],
    )

    _SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}

    def execute(self, context: SkillContext) -> SkillResult:
        if context.memory is None:
            return SkillResult(
                skill_name=self.metadata.name,
                success=False,
                data=None,
                error="Memory access denied — requires MEMORY_READ permission",
            )

        fmt = (context.params.get("format") or "markdown").lower().strip()
        if fmt not in _VALID_FORMATS:
            return SkillResult(
                skill_name=self.metadata.name,
                success=False,
                data=None,
                error=f"Invalid format '{fmt}'. Choose from: {', '.join(sorted(_VALID_FORMATS))}",
            )

        limit = context.params.get("limit", 25)
        domain_filter = (context.params.get("domain_filter") or "").lower().strip()
        min_severity = (context.params.get("min_severity") or "low").lower()
        min_rank = self._SEVERITY_RANK.get(min_severity, 0)

        records = context.memory.get_filing_history(
            domain=domain_filter or None,
            limit=limit,
        )

        # Filter by domain and severity
        rows: list[dict] = []
        for rec in records:
            filing = rec.content.get("filing", {})
            impact = rec.content.get("impact", {})

            if domain_filter and filing.get("domain", "").lower() != domain_filter:
                continue

            sev = (impact.get("severity") or "unknown").lower()
            if self._SEVERITY_RANK.get(sev, 0) < min_rank:
                continue

            rows.append(
                {
                    "filing_id": filing.get("id", rec.key),
                    "title": filing.get("title", ""),
                    "domain": (filing.get("domain") or "").upper(),
                    "change_type": filing.get("change_type", ""),
                    "published_date": filing.get("published_date", ""),
                    "severity": sev,
                    "affected_business_lines": ", ".join(impact.get("affected_business_lines", [])),
                    "affected_regulations": ", ".join(impact.get("affected_regulations", [])),
                    "compliance_deadline": impact.get("compliance_deadline") or "",
                    "action_items": impact.get("action_items", []),
                    "risk_summary": impact.get("risk_summary", ""),
                    "confidence": impact.get("confidence", 0.0),
                    "source_url": filing.get("source_url", ""),
                }
            )

        if not rows:
            content = _empty_content(fmt)
        elif fmt == "markdown":
            content = _to_markdown(rows, domain_filter, min_severity)
        elif fmt == "json":
            content = _to_json(rows)
        else:  # csv
            content = _to_csv(rows)

        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data={
                "format": fmt,
                "content": content,
                "row_count": len(rows),
                "metadata": {
                    "domain_filter": domain_filter or "all",
                    "min_severity": min_severity,
                    "total_records_scanned": len(records),
                },
            },
            metadata={"format": fmt, "rows": len(rows)},
        )


# ── Formatters ────────────────────────────────────────────────────────────────


def _empty_content(fmt: str) -> str:
    if fmt == "csv":
        return _csv_header()
    if fmt == "json":
        return "[]"
    return "# Regulatory Compliance Report\n\n_No analyses match the current filters._\n"


def _to_markdown(rows: list[dict], domain_filter: str, min_severity: str) -> str:
    from datetime import datetime

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    domain_label = domain_filter.upper() if domain_filter else "All Agencies"

    lines = [
        "# Regulatory Compliance Report",
        f"**Generated:** {now}  ",
        f"**Scope:** {domain_label}  ",
        f"**Minimum Severity:** {min_severity.capitalize()}  ",
        f"**Filings:** {len(rows)}",
        "",
        "---",
        "",
    ]

    sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}

    for row in rows:
        icon = sev_icon.get(row["severity"], "⚪")
        lines.append(f"## {icon} {row['title']}")
        lines.append(
            f"**ID:** `{row['filing_id']}` | **Domain:** {row['domain']} | "
            f"**Type:** {row['change_type']} | **Published:** {row['published_date']}"
        )
        lines.append(
            f"**Severity:** {row['severity'].upper()} | "
            f"**Confidence:** {row['confidence']:.0%} | "
            f"**Deadline:** {row['compliance_deadline'] or 'Not specified'}"
        )
        lines.append("")
        if row["risk_summary"]:
            lines.append(f"> {row['risk_summary']}")
            lines.append("")
        if row["affected_business_lines"]:
            lines.append(f"**Affected Business Lines:** {row['affected_business_lines']}")
        if row["affected_regulations"]:
            lines.append(f"**Cited Regulations:** {row['affected_regulations']}")
        if row["action_items"]:
            lines.append("**Action Items:**")
            for item in row["action_items"]:
                lines.append(f"- {item}")
        if row["source_url"]:
            lines.append(f"**Source:** [{row['source_url']}]({row['source_url']})")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def _to_json(rows: list[dict]) -> str:
    return json.dumps(rows, indent=2, default=str)


def _csv_header() -> str:
    return (
        "filing_id,title,domain,change_type,published_date,severity,"
        "affected_business_lines,affected_regulations,compliance_deadline,"
        "risk_summary,confidence,source_url\n"
    )


def _to_csv(rows: list[dict]) -> str:
    lines = [_csv_header().rstrip()]
    for row in rows:

        def _esc(val: str) -> str:
            val = str(val).replace('"', '""')
            return f'"{val}"' if ("," in val or '"' in val or "\n" in val) else val

        lines.append(
            ",".join(
                [
                    _esc(row["filing_id"]),
                    _esc(row["title"]),
                    _esc(row["domain"]),
                    _esc(row["change_type"]),
                    _esc(row["published_date"]),
                    _esc(row["severity"]),
                    _esc(row["affected_business_lines"]),
                    _esc(row["affected_regulations"]),
                    _esc(row["compliance_deadline"]),
                    _esc(row["risk_summary"]),
                    _esc(str(row["confidence"])),
                    _esc(row["source_url"]),
                ]
            )
        )
    return "\n".join(lines) + "\n"
