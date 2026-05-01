"""Skill: Counterparty Risk Analysis — SA-CCR, SIMM/UMR, CVA capital, and XVA impacts.

Analyses regulatory changes affecting SA-CCR exposure-at-default calculations,
initial margin requirements under SIMM/UMR, CVA capital charges, and netting
set eligibility. Directly actionable for Prime Lending and XVA desks managing
counterparty credit risk and margin optimisation.
"""

from app.naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)
from app.naturalsentinel.fetchers import DOMAIN_BUSINESS_LINES
from app.naturalsentinel.utils.parsing import parse_llm_json

COUNTERPARTY_RISK_SYSTEM = """\
You are a senior counterparty credit risk quant with deep expertise in SA-CCR \
(Standardised Approach for Counterparty Credit Risk), initial margin frameworks \
(ISDA SIMM, UMR phases), CVA capital charge methodologies (SA-CVA, BA-CVA), \
and XVA desk risk management.
Given a regulatory filing, extract all structured counterparty risk implications \
including EAD impacts, supervisory factor changes, initial margin deltas, CVA \
capital effects, MVA impacts, netting set modifications, and XVA recalibration needs.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "sa_ccr_ead_impact":              "increase" | "decrease" | "neutral" | "unknown",
  "supervisory_factor_changes":     [{"asset_class": <str>, "old_factor": <float>, "new_factor": <float>}],
  "initial_margin_change_pct":      <float — estimated IM change in percent; 0.0 if unknown>,
  "cva_capital_impact":             "increase" | "decrease" | "neutral" | "unknown",
  "mva_impact":                     "increase" | "decrease" | "neutral" | "unknown",
  "netting_set_changes":            [<string>],
  "counterparty_tier_impacts":      [<string>],
  "ead_delta_direction":            "increase" | "decrease" | "neutral" | "unknown",
  "xva_recalibration_required":     <bool>,
  "action_items":                   [<string>],
  "confidence":                     <float 0-1>,
  "summary":                        "<concise counterparty risk impact summary>"
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


class CounterpartyRiskSkill(Skill):
    metadata = SkillMetadata(
        name="counterparty_risk_analysis",
        description=(
            "Analyse SA-CCR, initial margin (SIMM/UMR), CVA capital charge, and "
            "counterparty credit risk framework changes. Maps regulatory changes to "
            "EAD impacts, IM requirement changes, CVA capital deltas, and netting set "
            "modifications — directly actionable for Prime Lending and XVA desks."
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
            "dict — {sa_ccr_ead_impact, supervisory_factor_changes, "
            "initial_margin_change_pct, cva_capital_impact, mva_impact, "
            "netting_set_changes, counterparty_tier_impacts, ead_delta_direction, "
            "xva_recalibration_required, action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "counterparty-risk",
            "sa-ccr",
            "simm",
            "cva",
            "ead",
            "xva",
            "prime-lending",
        ],
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

        raw = context.llm.complete(
            COUNTERPARTY_RISK_SYSTEM, user_prompt, temperature=0.1
        )

        fallback = {
            "sa_ccr_ead_impact": "neutral",
            "supervisory_factor_changes": [],
            "initial_margin_change_pct": 0.0,
            "cva_capital_impact": "neutral",
            "mva_impact": "neutral",
            "netting_set_changes": [],
            "counterparty_tier_impacts": [],
            "ead_delta_direction": "neutral",
            "xva_recalibration_required": False,
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
                "sa_ccr_ead_impact": parsed.get("sa_ccr_ead_impact"),
            },
        )
