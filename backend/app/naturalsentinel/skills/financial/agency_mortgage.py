"""Skill: Agency Mortgage Analysis — FHFA, Fannie Mae, Freddie Mac, and Ginnie Mae impacts.

Parses regulatory changes from GSE conservators and issuers for Agency Lending
desk impacts. Surfaces conforming limit changes, g-fee adjustments, collateral
haircut updates, CRT program changes, and TBA eligibility impacts. Designed for
Agency Lending, MBS trading, and hedging desks operating in GSE-backed markets.
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

AGENCY_MORTGAGE_SYSTEM = """\
You are a senior agency MBS and GSE regulatory specialist with deep expertise in \
FHFA conservatorship rules, Fannie Mae/Freddie Mac Selling and Servicing Guides, \
Ginnie Mae MBS program requirements, conforming loan limits (FHFA HERA adjustments), \
guarantee fee (g-fee) structures, credit risk transfer (CRT) programmes (CAS, STACR), \
TBA eligibility (SIFMA/TBMA good delivery guidelines), and prepayment / hedging \
dynamics in agency pass-through and CMO markets.
Given a regulatory filing, identify all implications for agency lending programmes, \
collateral haircut schedules, CRT structures, TBA eligibility, prepayment model \
assumptions, and desk-level hedging strategies.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "conforming_limit_changes":        {"standard": <float or null>, "high_balance": <float or null>, "change_effective_date": <str or null>},
  "gfee_adjustments":                [{"loan_type": <str>, "old_gfee_bps": <float>, "new_gfee_bps": <float>, "rationale": <str>}],
  "collateral_haircut_updates":      [{"pool_type": <str>, "old_haircut": <float>, "new_haircut": <float>}],
  "crt_program_changes":             [<string>],
  "tba_eligibility_changes":         [<string>],
  "prepayment_model_implications":   [<string>],
  "hedging_implications":            [<string>],
  "agency_lending_program_impacts":  [<string>],
  "desk_action_items":               [<string>],
  "confidence":                      <float 0-1>,
  "summary":                         "<concise agency mortgage impact summary>"
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


class AgencyMortgageSkill(Skill):
    metadata = SkillMetadata(
        name="agency_mortgage_analysis",
        description=(
            "Parse FHFA, Fannie Mae, Freddie Mac, and Ginnie Mae regulatory changes "
            "for Agency Lending desk impacts. Surfaces conforming limit changes, g-fee "
            "adjustments, collateral haircut updates, CRT program changes, and TBA "
            "eligibility impacts."
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
            "dict — {conforming_limit_changes, gfee_adjustments, "
            "collateral_haircut_updates, crt_program_changes, tba_eligibility_changes, "
            "prepayment_model_implications, hedging_implications, "
            "agency_lending_program_impacts, desk_action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "agency-lending",
            "fhfa",
            "gse",
            "fannie",
            "freddie",
            "tba",
            "mbs",
            "crt",
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

        raw = context.llm.complete(AGENCY_MORTGAGE_SYSTEM, user_prompt, temperature=0.1)

        fallback = {
            "conforming_limit_changes": {},
            "gfee_adjustments": [],
            "collateral_haircut_updates": [],
            "crt_program_changes": [],
            "tba_eligibility_changes": [],
            "prepayment_model_implications": [],
            "hedging_implications": [],
            "agency_lending_program_impacts": [],
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
                "tba_eligibility_changes": parsed.get("tba_eligibility_changes"),
            },
        )
