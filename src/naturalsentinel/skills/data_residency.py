"""Skill: Data Residency Obligation — map data localisation and cross-border transfer obligations from regulatory filings.

Designed for cloud architects, data governance teams, and international compliance
counsel. Parses a regulatory filing for structured data residency obligations including
jurisdiction-specific storage mandates, SCC/BCR changes, adequacy decision impacts,
and cloud sovereignty requirements.
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

DATA_RESIDENCY_SYSTEM = """\
You are a senior data localisation and cross-border transfer specialist with expertise \
in GDPR Chapter V transfer mechanisms (SCCs, BCRs, adequacy decisions), EU-US Data \
Privacy Framework, China PIPL/DSL cross-border rules, and India DPDP Act transfer \
provisions.
Your task is to extract structured data residency and cross-border transfer obligation \
data from a regulatory filing.
Identify implications for data localisation requirements, cross-border transfer \
mechanism changes, adequacy decision impacts, cloud sovereignty mandates, government \
access framework changes, sector-specific localisation rules, third-country transfer \
prohibitions, infrastructure location mandates, and the overall direction of compliance \
cost impact.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "data_localization_requirements":          [<string>],
  "cross_border_transfer_mechanism_changes": [<string>],
  "adequacy_decision_impacts":               [<string>],
  "cloud_sovereignty_implications":          [<string>],
  "government_access_framework_changes":     [<string>],
  "sector_specific_requirements":            [<string>],
  "third_country_transfer_prohibitions":     [<string>],
  "infrastructure_location_mandates":        [<string>],
  "compliance_cost_direction":               "increase" | "decrease" | "neutral" | "unknown",
  "action_items":                            [<string>],
  "confidence":                              <float 0-1>,
  "summary":                                 "<concise summary>"
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


class DataResidencySkill(Skill):
    metadata = SkillMetadata(
        name="data_residency_obligation",
        description=(
            "Map data localisation and cross-border transfer obligations from regulatory "
            "filings — identifies jurisdiction-specific storage mandates, SCC/BCR "
            "changes, adequacy decision impacts, and cloud sovereignty requirements. "
            "Actionable for cloud architects, data governance teams, and international "
            "compliance counsel."
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
            "dict — {data_localization_requirements, cross_border_transfer_mechanism_changes, "
            "adequacy_decision_impacts, cloud_sovereignty_implications, "
            "government_access_framework_changes, sector_specific_requirements, "
            "third_country_transfer_prohibitions, infrastructure_location_mandates, "
            "compliance_cost_direction, action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "data-residency",
            "localisation",
            "cross-border",
            "sccs",
            "adequacy",
            "cloud-sovereignty",
            "gdpr-transfers",
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

        raw = context.llm.complete(DATA_RESIDENCY_SYSTEM, user_prompt, temperature=0.1)

        fallback = {
            "data_localization_requirements": [],
            "cross_border_transfer_mechanism_changes": [],
            "adequacy_decision_impacts": [],
            "cloud_sovereignty_implications": [],
            "government_access_framework_changes": [],
            "sector_specific_requirements": [],
            "third_country_transfer_prohibitions": [],
            "infrastructure_location_mandates": [],
            "compliance_cost_direction": "unknown",
            "action_items": [],
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
                "compliance_cost_direction": parsed.get("compliance_cost_direction"),
            },
        )
