"""Skill: Content Moderation Liability Analysis — map Section 230 reform signals, DSA VLOP obligations, notice-and-takedown changes, and algorithmic amplification restrictions.

Designed for trust and safety teams, policy counsel, and platform compliance professionals
building structured workflows around evolving content liability frameworks. Parses a
regulatory filing for actionable platform content moderation implications under US and EU
frameworks.
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

CONTENT_MODERATION_SYSTEM = """\
You are a senior platform liability and content law specialist with expertise in CDA \
Section 230, EU Digital Services Act (DSA), Online Safety Act (UK), and FOSTA-SESTA \
precedent.
Your task is to extract structured content moderation liability data from a regulatory filing.
Identify implications for Section 230 liability exposure, DSA/VLOP compliance obligations, \
mandatory removal or retention requirements, notice-and-takedown processes, transparency \
reporting, algorithmic amplification restrictions, designated harmful content categories, \
overall liability exposure direction, and platform size tier impacts.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "section_230_implications":              [<string>],
  "dsa_compliance_changes":                [<string>],
  "removal_obligation_changes":            [<string>],
  "notice_and_takedown_changes":           [<string>],
  "transparency_report_obligations":       [<string>],
  "algorithmic_amplification_restrictions":[<string>],
  "designated_content_changes":            [<string>],
  "liability_exposure_direction":          "increase" | "decrease" | "neutral" | "unknown",
  "platform_size_tier_impacts":            [<string>],
  "action_items":                          [<string>],
  "confidence":                            <float 0-1>,
  "summary":                               "<concise content moderation liability summary>"
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


class ContentModerationSkill(Skill):
    metadata = SkillMetadata(
        name="content_moderation_liability",
        description=(
            "Assess platform content liability changes from regulatory filings — maps "
            "Section 230 reform signals, DSA Very Large Online Platform (VLOP) obligations, "
            "notice-and-takedown changes, and algorithmic amplification restrictions. "
            "Actionable for trust and safety teams, policy counsel, and platform compliance."
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
            "dict — {section_230_implications, dsa_compliance_changes, "
            "removal_obligation_changes, notice_and_takedown_changes, "
            "transparency_report_obligations, algorithmic_amplification_restrictions, "
            "designated_content_changes, liability_exposure_direction, "
            "platform_size_tier_impacts, action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "content-moderation",
            "section-230",
            "dsa",
            "vlop",
            "takedown",
            "trust-safety",
            "platform-liability",
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
            CONTENT_MODERATION_SYSTEM, user_prompt, temperature=0.1
        )

        fallback = {
            "section_230_implications": [],
            "dsa_compliance_changes": [],
            "removal_obligation_changes": [],
            "notice_and_takedown_changes": [],
            "transparency_report_obligations": [],
            "algorithmic_amplification_restrictions": [],
            "designated_content_changes": [],
            "liability_exposure_direction": "unknown",
            "platform_size_tier_impacts": [],
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
                "liability_exposure_direction": parsed.get(
                    "liability_exposure_direction"
                ),
            },
        )
