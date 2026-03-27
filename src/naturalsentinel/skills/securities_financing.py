"""Skill: Securities Financing Analysis — repo, reverse repo, sec lending, and TBA impacts.

Surfaces regulatory changes affecting collateral schedules, haircut matrices,
rehypothecation limits, settlement frameworks, and SFTR reporting obligations.
Directly actionable for Secured Lending, Agency Lending, and Prime desks.
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

SECURITIES_FINANCING_SYSTEM = """\
You are a senior securities finance specialist with deep expertise in repo, \
reverse repo, securities lending, TBA markets, SFTR reporting, and prime \
brokerage regulation (EMIR, Dodd-Frank, Basel III margin rules).
Given a regulatory filing, identify all implications for securities financing \
markets: collateral eligibility, haircut schedules, rehypothecation limits, \
settlement frameworks, margin requirements, and SFTR/DTCC reporting obligations.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "rehypothecation_impact":        "restricted" | "expanded" | "none" | "unknown",
  "haircut_changes":               [{"asset_class": <str>, "old_haircut_pct": <float>, "new_haircut_pct": <float>}],
  "collateral_eligibility_changes":[<string>],
  "repo_market_impact":            "tightens" | "loosens" | "neutral" | "unknown",
  "settlement_framework_changes":  [<string>],
  "sftr_reporting_changes":        [<string>],
  "margin_requirement_changes":    [<string>],
  "prime_brokerage_impacts":       [<string>],
  "desk_action_items":             [<string>],
  "confidence":                    <float 0-1>,
  "summary":                       "<concise securities financing impact summary>"
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


class SecuritiesFinancingSkill(Skill):
    metadata = SkillMetadata(
        name="securities_financing_analysis",
        description=(
            "Analyse regulatory changes affecting repo, reverse repo, securities "
            "lending, and TBA markets. Surfaces impacts on collateral schedules, "
            "haircut matrices, rehypothecation limits, settlement frameworks, and "
            "SFTR reporting — directly actionable for Secured Lending, Agency "
            "Lending, and Prime desks."
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
            "dict — {rehypothecation_impact, haircut_changes, "
            "collateral_eligibility_changes, repo_market_impact, "
            "settlement_framework_changes, sftr_reporting_changes, "
            "margin_requirement_changes, prime_brokerage_impacts, "
            "desk_action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "securities-lending",
            "repo",
            "tba",
            "collateral",
            "haircut",
            "prime",
            "sftr",
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
            SECURITIES_FINANCING_SYSTEM, user_prompt, temperature=0.1
        )

        fallback = {
            "rehypothecation_impact": "none",
            "haircut_changes": [],
            "collateral_eligibility_changes": [],
            "repo_market_impact": "neutral",
            "settlement_framework_changes": [],
            "sftr_reporting_changes": [],
            "margin_requirement_changes": [],
            "prime_brokerage_impacts": [],
            "desk_action_items": ["Manual review required"],
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
                "repo_market_impact": parsed.get("repo_market_impact"),
            },
        )
