"""Skill: Cross-Domain Correlation — find regulatory overlaps across agencies.

Many regulatory changes ripple across multiple agencies.  This skill
identifies business lines that appear in analyses from *more than one* domain,
surfaces shared affected regulations, and uses the LLM to summarise the
compounded compliance burden.

Example: An AI/ML medical device (FDA) that also handles consumer financial
data (CFPB) faces dual regimes.  This skill flags those intersections.
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

_CROSS_DOMAIN_SYSTEM = """\
You are a senior regulatory counsel specialising in multi-agency compliance.
You receive a list of regulatory intersections — business lines regulated by
more than one agency simultaneously.
Identify the highest-risk intersections, explain the compounded burden, and
recommend which legal/compliance teams should collaborate.
Max 300 words. Structured prose only — no bullet points unless quoting specifics.
"""

_CROSS_DOMAIN_USER = """\
Cross-domain regulatory intersections detected:

{intersections}

For each intersection, the business line is subject to filings from multiple
agencies listed. Assess: which intersections create the most complex compliance
environment and what immediate coordination actions are required?
"""


class CrossDomainCorrelationSkill(Skill):
    metadata = SkillMetadata(
        name="cross_domain_correlation",
        description=(
            "Identify business lines simultaneously regulated by multiple agencies "
            "within the stored analyses. Returns intersection maps showing which "
            "business lines appear in filings from more than one regulatory domain, "
            "their combined action item list, and an optional LLM assessment of the "
            "compound compliance burden."
        ),
        version="1.0.0",
        permissions=Permission.MEMORY_READ | Permission.LLM_READ,
        latency=LatencyClass.MODERATE,
        parameters=[
            SkillParameter(
                "min_domains",
                "int",
                "Minimum number of distinct domains a business line must appear in to flag (default 2).",
                required=False,
                default=2,
            ),
            SkillParameter(
                "limit",
                "int",
                "Number of recent analyses to inspect.",
                required=False,
                default=100,
            ),
            SkillParameter(
                "include_assessment",
                "bool",
                "Generate an LLM assessment of the compound burden (requires LLM_READ).",
                required=False,
                default=True,
            ),
        ],
        returns=(
            "dict — {intersections: list[dict], assessment: str | None} where each "
            "intersection has business_line, domains, combined_action_items, "
            "combined_regulations, max_severity, filing_count."
        ),
        dependencies=[],
        cacheable=False,
        tags=["cross-domain", "correlation", "analysis", "multi-agency"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        if context.memory is None:
            return SkillResult(
                skill_name=self.metadata.name,
                success=False,
                data=None,
                error="Memory access denied — requires MEMORY_READ permission",
            )

        min_domains = context.params.get("min_domains", 2)
        limit = context.params.get("limit", 100)
        include_assessment = context.params.get("include_assessment", True)

        records = context.memory.get_filing_history(limit=limit)
        if not records:
            return SkillResult(
                skill_name=self.metadata.name,
                success=True,
                data={"intersections": [], "assessment": "No data in memory."},
                metadata={"message": "No analyses found."},
            )

        # ── Build: business_line → {domain → [filing info]} ─────────────────
        bl_to_domains: dict[str, dict[str, list[dict]]] = defaultdict(
            lambda: defaultdict(list)
        )

        severity_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}

        for rec in records:
            filing = rec.content.get("filing", {})
            impact = rec.content.get("impact", {})

            domain = (filing.get("domain") or "unknown").lower()
            for bl in impact.get("affected_business_lines", []):
                bl_to_domains[bl][domain].append(
                    {
                        "filing_id": filing.get("id", rec.key),
                        "title": filing.get("title", "Unknown"),
                        "severity": (impact.get("severity") or "unknown").lower(),
                        "action_items": impact.get("action_items", []),
                        "affected_regulations": impact.get("affected_regulations", []),
                        "deadline": impact.get("compliance_deadline"),
                    }
                )

        # ── Filter to intersections spanning ≥ min_domains ──────────────────
        intersections: list[dict] = []
        for bl, domain_map in bl_to_domains.items():
            if len(domain_map) < min_domains:
                continue

            all_actions: list[str] = []
            all_regs: list[str] = []
            all_severities: list[int] = []
            filing_count = 0

            for domain, filings in domain_map.items():
                filing_count += len(filings)
                for f in filings:
                    all_actions.extend(f["action_items"])
                    all_regs.extend(f["affected_regulations"])
                    all_severities.append(severity_rank.get(f["severity"], 0))

            # Deduplicate while preserving order
            seen_actions: set[str] = set()
            deduped_actions = []
            for a in all_actions:
                if a not in seen_actions:
                    seen_actions.add(a)
                    deduped_actions.append(a)

            seen_regs: set[str] = set()
            deduped_regs = []
            for r in all_regs:
                if r not in seen_regs:
                    seen_regs.add(r)
                    deduped_regs.append(r)

            max_sev_rank = max(all_severities) if all_severities else 0
            rank_to_name = {0: "low", 1: "medium", 2: "high", 3: "critical"}

            intersections.append(
                {
                    "business_line": bl,
                    "domains": sorted(domain_map.keys()),
                    "domain_count": len(domain_map),
                    "filing_count": filing_count,
                    "max_severity": rank_to_name[max_sev_rank],
                    "combined_action_items": deduped_actions,
                    "combined_regulations": deduped_regs,
                    "domain_breakdown": {
                        dom: [
                            {
                                "id": f["filing_id"],
                                "title": f["title"],
                                "severity": f["severity"],
                            }
                            for f in filings
                        ]
                        for dom, filings in domain_map.items()
                    },
                }
            )

        # Sort: most domains first, then max severity descending
        intersections.sort(
            key=lambda x: (-x["domain_count"], -severity_rank.get(x["max_severity"], 0))
        )

        # ── Optional LLM assessment ───────────────────────────────────────────
        assessment: str | None = None
        token_usage = 0
        if include_assessment and intersections and context.llm is not None:
            intersection_text = "\n".join(
                f"- {ix['business_line']}: regulated by {', '.join(d.upper() for d in ix['domains'])} "
                f"(max severity: {ix['max_severity']}, {ix['filing_count']} filings)"
                for ix in intersections[:15]  # Cap to avoid token overflow
            )
            user_prompt = _CROSS_DOMAIN_USER.format(intersections=intersection_text)
            assessment = context.llm.complete(
                _CROSS_DOMAIN_SYSTEM, user_prompt, temperature=0.2
            )
            token_usage = len(user_prompt) // 4 + len(assessment) // 4

        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data={
                "intersections": intersections,
                "assessment": assessment,
                "summary": {
                    "total_business_lines_checked": len(bl_to_domains),
                    "intersections_found": len(intersections),
                    "min_domains_threshold": min_domains,
                },
            },
            token_usage=token_usage,
            metadata={"intersections_found": len(intersections)},
        )
