"""Skill: Spectrum Licensing Change Analysis — surface band-specific impacts on licensing, auction procedures, power limits, and build-out obligations from FCC spectrum rulemaking.

Designed for spectrum management teams and FCC regulatory affairs professionals at
wireless carriers, satellite operators, and private network deployors. Parses a
regulatory filing for structured spectrum licensing implications across FCC frameworks.
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

SPECTRUM_LICENSING_SYSTEM = """\
You are a senior FCC spectrum policy expert with expertise in spectrum auctions, Part 96 \
CBRS rules, C-band transition, RDOF/BEAD broadband funding, and international spectrum \
coordination (ITU).
Your task is to extract structured spectrum licensing change data from a regulatory filing.
Identify implications for band-specific license changes, power limits, interference \
protection rules, auction procedures, build-out milestones, equipment authorization, \
compliance timelines, and incumbent relocation obligations.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "band_affected":                      "<string — e.g. C-band 3.7-4.2 GHz; null if unknown>",
  "license_type_changes":               [<string>],
  "power_limit_changes":                [<string>],
  "interference_protection_changes":    [<string>],
  "auction_implications":               [<string>],
  "build_out_requirement_changes":      [<string>],
  "equipment_authorization_changes":    [<string>],
  "timeline_milestones":                [<string>],
  "incumbent_relocation_requirements":  [<string>],
  "action_items":                       [<string>],
  "confidence":                         <float 0-1>,
  "summary":                            "<concise spectrum licensing change summary>"
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


class SpectrumLicensingSkill(Skill):
    metadata = SkillMetadata(
        name="spectrum_licensing_change",
        description=(
            "Analyse FCC spectrum rulemaking for licensing, auction, power limit, and "
            "build-out obligation changes. Surfaces band-specific impacts on wireless "
            "carriers, satellite operators, and private network deployors. Actionable for "
            "spectrum management teams and FCC regulatory affairs."
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
            "dict — {band_affected, license_type_changes, power_limit_changes, "
            "interference_protection_changes, auction_implications, "
            "build_out_requirement_changes, equipment_authorization_changes, "
            "timeline_milestones, incumbent_relocation_requirements, "
            "action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "spectrum",
            "fcc",
            "licensing",
            "auction",
            "5g",
            "wireless",
            "cbrs",
            "c-band",
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
            SPECTRUM_LICENSING_SYSTEM, user_prompt, temperature=0.1
        )

        fallback = {
            "band_affected": "null if unknown",
            "license_type_changes": [],
            "power_limit_changes": [],
            "interference_protection_changes": [],
            "auction_implications": [],
            "build_out_requirement_changes": [],
            "equipment_authorization_changes": [],
            "timeline_milestones": [],
            "incumbent_relocation_requirements": [],
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
                "band_affected": parsed.get("band_affected"),
            },
        )
