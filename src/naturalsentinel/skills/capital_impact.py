"""Skill: Capital Impact Analysis — estimate RWA, SLR, leverage, and output floor effects.

Designed for Capital Optimization desks and data scientists building capital
allocation models. Parses a regulatory filing for structured capital implications
including RWA delta estimates, SLR impact, leverage ratio effects, and output
floor consequences under Basel III/IV frameworks.
"""

from naturalsentinel.agent_framework import (
    Skill, SkillMetadata, SkillParameter, SkillContext, SkillResult,
    Permission, LatencyClass,
)
from naturalsentinel.fetchers import DOMAIN_BUSINESS_LINES
from naturalsentinel.utils.parsing import parse_llm_json


CAPITAL_IMPACT_SYSTEM = """\
You are a senior bank capital management analyst specialising in Basel III/IV, \
CRR2/CRD5, and US prudential capital frameworks (SCB, GSIB surcharge, TLAC).
Your task is to extract structured capital impact data from a regulatory filing.
Identify implications for Risk-Weighted Assets (RWA), the Supplementary Leverage \
Ratio (SLR), leverage ratio requirements, and the Basel IV output floor.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "rwa_impact_direction":           "increase" | "decrease" | "neutral" | "unknown",
  "rwa_pct_change_estimate":        <float — basis-point estimate; 0.0 if unknown>,
  "slr_impact_direction":           "increase" | "decrease" | "neutral" | "unknown",
  "leverage_ratio_impact":          "tightens" | "loosens" | "neutral" | "unknown",
  "output_floor_relevance":         <bool>,
  "affected_capital_metrics":       [<string>],
  "capital_cost_per_trade_bps":     <float — 0.0 if unknown>,
  "optimization_constraint_changes":[<string>],
  "model_recalibration_required":   <bool>,
  "confidence":                     <float 0-1>,
  "summary":                        "<concise capital impact summary>"
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


class CapitalImpactSkill(Skill):
    metadata = SkillMetadata(
        name="capital_impact",
        description=(
            "Analyse a regulatory filing for capital implications — estimates RWA "
            "delta, SLR impact, leverage ratio effects, and output floor consequences. "
            "Designed for Capital Optimization desks and data scientists building "
            "capital allocation models."
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
            "dict — {rwa_impact_direction, rwa_pct_change_estimate, slr_impact_direction, "
            "leverage_ratio_impact, output_floor_relevance, affected_capital_metrics, "
            "capital_cost_per_trade_bps, optimization_constraint_changes, "
            "model_recalibration_required, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=["capital", "rwa", "slr", "leverage", "optimization", "basel"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        if context.llm is None:
            return SkillResult(
                skill_name=self.metadata.name, success=False, data=None,
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

        raw = context.llm.complete(CAPITAL_IMPACT_SYSTEM, user_prompt, temperature=0.1)

        fallback = {
            "rwa_impact_direction": "unknown",
            "rwa_pct_change_estimate": 0.0,
            "slr_impact_direction": "neutral",
            "leverage_ratio_impact": "neutral",
            "output_floor_relevance": False,
            "affected_capital_metrics": [],
            "capital_cost_per_trade_bps": 0.0,
            "optimization_constraint_changes": [],
            "model_recalibration_required": False,
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
                "rwa_impact_direction": parsed.get("rwa_impact_direction"),
            },
        )
