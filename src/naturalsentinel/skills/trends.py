"""Skill: Trend Analysis — detect patterns and escalation across regulatory history.

Analyses the distribution and trajectory of severities, change types, and
active domains over time. Returns trend signals (stable / escalating /
de-escalating) and a natural-language LLM-generated narrative summary.
"""

from __future__ import annotations

from collections import defaultdict

from naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}

_TREND_SYSTEM = """\
You are a quantitative regulatory analyst. You receive aggregated statistics \
about regulatory filings across multiple agencies and time windows.
Your job is to identify trends, surface escalation signals, and highlight \
which business lines face increasing regulatory pressure.
Write in plain prose — no tables. Max 200 words. No filler.
"""

_TREND_USER = """\
Analyse the following regulatory trend data and summarise key findings:

Window A (older half): {window_a}
Window B (recent half): {window_b}

Severity distribution (all time): {severity_dist}
Domain activity (all time): {domain_dist}
Most common change types: {change_type_dist}
Most impacted business lines: {top_business_lines}

Identify: escalation signals, de-escalation, and domains with notably high activity.
"""


class TrendAnalysisSkill(Skill):
    metadata = SkillMetadata(
        name="trend_analysis",
        description=(
            "Analyse historical filing data in memory to detect regulatory "
            "trends. Splits the history into two windows and compares severity "
            "distributions to identify escalating or de-escalating pressure by "
            "domain. Produces statistical outputs plus an optional LLM narrative."
        ),
        version="1.0.0",
        permissions=Permission.MEMORY_READ | Permission.LLM_READ,
        latency=LatencyClass.MODERATE,
        parameters=[
            SkillParameter(
                "limit",
                "int",
                "Number of recent analyses to include in the trend window.",
                required=False,
                default=50,
            ),
            SkillParameter(
                "include_narrative",
                "bool",
                "Generate an LLM narrative summary of the trends (requires LLM_READ).",
                required=False,
                default=True,
            ),
        ],
        returns=(
            "dict — {statistics: dict, trend_signals: list[dict], "
            "narrative: str | None} where trend_signals has domain, "
            "signal ('escalating'|'stable'|'de-escalating'), and detail."
        ),
        dependencies=[],
        cacheable=False,
        tags=["trends", "analysis", "patterns", "intelligence"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        if context.memory is None:
            return SkillResult(
                skill_name=self.metadata.name,
                success=False,
                data=None,
                error="Memory access denied — requires MEMORY_READ permission",
            )

        limit = context.params.get("limit", 50)
        include_narrative = context.params.get("include_narrative", True)

        records = context.memory.get_filing_history(limit=limit)
        if not records:
            return SkillResult(
                skill_name=self.metadata.name,
                success=True,
                data={
                    "statistics": {},
                    "trend_signals": [],
                    "narrative": "No data in memory.",
                },
                metadata={"message": "No analyses found. Run a scan cycle first."},
            )

        # ── Aggregate over full history ──────────────────────────────────────
        severity_dist: dict[str, int] = defaultdict(int)
        domain_dist: dict[str, int] = defaultdict(int)
        change_type_dist: dict[str, int] = defaultdict(int)
        business_line_counts: dict[str, int] = defaultdict(int)
        domain_severity: dict[str, list[int]] = defaultdict(list)

        for rec in records:
            filing = rec.content.get("filing", {})
            impact = rec.content.get("impact", {})

            sev = (impact.get("severity") or "unknown").lower()
            dom = (filing.get("domain") or "unknown").lower()
            ct = (filing.get("change_type") or "unknown").lower()

            severity_dist[sev] += 1
            domain_dist[dom] += 1
            change_type_dist[ct] += 1
            domain_severity[dom].append(_SEVERITY_RANK.get(sev, 0))

            for bl in impact.get("affected_business_lines", []):
                business_line_counts[bl] += 1

        # ── Split into two temporal windows for trajectory ───────────────────
        mid = max(1, len(records) // 2)
        older_half = records[mid:]  # get_filing_history returns newest-first
        newer_half = records[:mid]

        def _window_stats(window: list) -> dict[str, dict[str, int]]:
            by_domain: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for rec in window:
                dom = (rec.content.get("filing", {}).get("domain") or "unknown").lower()
                sev = (
                    rec.content.get("impact", {}).get("severity") or "unknown"
                ).lower()
                by_domain[dom][sev] += 1
            return {k: dict(v) for k, v in by_domain.items()}

        window_a = _window_stats(older_half)
        window_b = _window_stats(newer_half)

        # ── Compute per-domain trend signal ──────────────────────────────────
        trend_signals: list[dict] = []
        for dom in set(list(window_a.keys()) + list(window_b.keys())):
            a_score = _avg_severity_score(window_a.get(dom, {}))
            b_score = _avg_severity_score(window_b.get(dom, {}))
            delta = b_score - a_score
            signal = "stable"
            if delta > 0.4:
                signal = "escalating"
            elif delta < -0.4:
                signal = "de-escalating"

            trend_signals.append(
                {
                    "domain": dom.upper(),
                    "signal": signal,
                    "avg_severity_older": round(a_score, 2),
                    "avg_severity_recent": round(b_score, 2),
                    "delta": round(delta, 2),
                    "filing_count": domain_dist.get(dom, 0),
                }
            )

        # Sort: escalating first, then by delta descending
        trend_signals.sort(
            key=lambda x: (
                -{"escalating": 2, "stable": 1, "de-escalating": 0}.get(x["signal"], 0),
                -x["delta"],
            )
        )

        top_business_lines = sorted(business_line_counts.items(), key=lambda x: -x[1])[
            :10
        ]

        stats = {
            "total_filings_analyzed": len(records),
            "severity_distribution": dict(severity_dist),
            "domain_activity": dict(domain_dist),
            "change_type_distribution": dict(change_type_dist),
            "top_affected_business_lines": [
                {"name": k, "count": v} for k, v in top_business_lines
            ],
        }

        # ── Optional LLM narrative ────────────────────────────────────────────
        narrative: str | None = None
        token_usage = 0
        if include_narrative and context.llm is not None:
            user_prompt = _TREND_USER.format(
                window_a=str(window_a),
                window_b=str(window_b),
                severity_dist=dict(severity_dist),
                domain_dist=dict(domain_dist),
                change_type_dist=dict(change_type_dist),
                top_business_lines=[k for k, _ in top_business_lines],
            )
            narrative = context.llm.complete(
                _TREND_SYSTEM, user_prompt, temperature=0.3
            )
            token_usage = len(user_prompt) // 4 + len(narrative) // 4

        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data={
                "statistics": stats,
                "trend_signals": trend_signals,
                "narrative": narrative,
            },
            token_usage=token_usage,
            metadata={"filings_analyzed": len(records)},
        )


def _avg_severity_score(severity_counts: dict[str, int]) -> float:
    """Compute the average severity score (0-3) from a {severity: count} dict."""
    total_weight = 0
    total_count = 0
    for sev, count in severity_counts.items():
        total_weight += _SEVERITY_RANK.get(sev, 0) * count
        total_count += count
    return total_weight / total_count if total_count else 0.0
