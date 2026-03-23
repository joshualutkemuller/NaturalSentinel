"""Skill: Liquidity Ratio Analysis — LCR, NSFR, and HQLA classification impacts.

Analyses regulatory changes for HQLA reclassification, LCR/NSFR treatment
changes, and balance sheet liquidity implications. Feeds directly into balance
sheet optimisation and ALM models for Financing Solutions desks and Treasury.
"""

from naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)
from naturalsentinel.fetchers import DOMAIN_BUSINESS_LINES
from naturalsentinel.utils.parsing import parse_llm_json

LIQUIDITY_RATIO_SYSTEM = """\
You are a senior ALM and liquidity risk analyst with deep expertise in Basel III \
LCR (Liquidity Coverage Ratio), NSFR (Net Stable Funding Ratio), HQLA \
classification (Level 1 / 2A / 2B), and US LCR rules (12 CFR Part 249).
Given a regulatory filing, identify all implications for liquidity ratios, \
HQLA eligibility, funding cost, and balance sheet optimisation constraints.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "hqla_classification_changes":        [{"asset_type": <str>, "old_level": <str>, "new_level": <str>}],
  "lcr_impact_direction":               "increase" | "decrease" | "neutral" | "unknown",
  "lcr_delta_estimate_pct":             <float — 0.0 if unknown>,
  "nsfr_impact_direction":              "increase" | "decrease" | "neutral" | "unknown",
  "nsfr_asf_rsf_changes":               [<string>],
  "liquidity_buffer_implications":      [<string>],
  "funding_cost_impact":                "increases" | "decreases" | "neutral" | "unknown",
  "balance_sheet_optimization_constraints": [<string>],
  "action_items":                       [<string>],
  "confidence":                         <float 0-1>,
  "summary":                            "<concise liquidity impact summary>"
}
"""

_USER_TEMPLATE = """\
FILING ID:      {filing_id}
DOMAIN:         {domain}
TITLE:          {title}
PUBLISHED DATE: {published_date}
SOURCE URL:     {source_url}
BUSINESS LINES: {business_lines}

FILING TEXT:
{raw_text}
{memory_block}\
"""


class LiquidityRatioSkill(Skill):
    metadata = SkillMetadata(
        name="liquidity_ratio_analysis",
        description=(
            "Analyse regulatory changes for HQLA classification impacts, LCR/NSFR "
            "treatment changes, and balance sheet liquidity implications. Feeds "
            "directly into balance sheet optimization and ALM models for Financing "
            "Solutions desks."
        ),
        version="1.0.0",
        permissions=Permission.LLM_READ | Permission.LLM_WRITE | Permission.MEMORY_READ,
        latency=LatencyClass.MODERATE,
        parameters=[
            SkillParameter(
                "filing",
                "dict",
                "Serialized RegulatoryFiling with id, title, domain, raw_text, etc.",
            ),
            SkillParameter(
                "memory_context",
                "str",
                "Pre-built memory context block to append to the prompt.",
                required=False,
                default="",
            ),
        ],
        returns=(
            "dict — {hqla_classification_changes, lcr_impact_direction, "
            "lcr_delta_estimate_pct, nsfr_impact_direction, nsfr_asf_rsf_changes, "
            "liquidity_buffer_implications, funding_cost_impact, "
            "balance_sheet_optimization_constraints, action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=["liquidity", "lcr", "nsfr", "hqla", "alm", "balance-sheet", "financing"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        if context.llm is None:
            return SkillResult(
                skill_name=self.metadata.name,
                success=False,
                data=None,
                error="LLM access denied — this skill requires LLM_READ permission",
            )

        filing = context.params["filing"]
        memory_context = context.params.get("memory_context", "")
        domain = filing.get("domain", "")
        domain_lines = DOMAIN_BUSINESS_LINES.get(domain, [])

        memory_block = ("\n" + memory_context) if memory_context else ""

        user_prompt = _USER_TEMPLATE.format(
            filing_id=filing.get("id", "UNKNOWN"),
            domain=domain.upper(),
            title=filing.get("title", ""),
            published_date=filing.get("published_date", ""),
            source_url=filing.get("source_url", ""),
            raw_text=filing.get("raw_text", ""),
            business_lines=", ".join(domain_lines),
            memory_block=memory_block,
        )

        raw = context.llm.complete(LIQUIDITY_RATIO_SYSTEM, user_prompt, temperature=0.1)

        fallback = {
            "hqla_classification_changes": [],
            "lcr_impact_direction": "neutral",
            "lcr_delta_estimate_pct": 0.0,
            "nsfr_impact_direction": "neutral",
            "nsfr_asf_rsf_changes": [],
            "liquidity_buffer_implications": [],
            "funding_cost_impact": "neutral",
            "balance_sheet_optimization_constraints": [],
            "action_items": ["Manual review required"],
            "confidence": 0.3,
            "summary": raw[:500],
        }
        parsed = parse_llm_json(raw, fallback=fallback)

        parsed["filing_id"] = filing.get("id", "UNKNOWN")
        parsed["domain"] = domain

        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data=parsed,
            token_usage=len(user_prompt) // 4 + len(raw) // 4,
            metadata={
                "filing_id": filing.get("id"),
                "lcr_impact_direction": parsed.get("lcr_impact_direction"),
            },
        )
