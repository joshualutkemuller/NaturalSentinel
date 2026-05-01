"""Skill: Data Privacy Obligation Analysis — map GDPR, CCPA, and state privacy law changes to data subject rights, consent frameworks, cross-border transfer mechanisms, and breach notification timelines.

Designed for DPOs, privacy engineering, and compliance teams building structured
workflows around evolving data protection obligations. Parses a regulatory filing
for actionable privacy compliance implications across global and US state frameworks.
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

DATA_PRIVACY_SYSTEM = """\
You are a senior data protection counsel with expertise in GDPR, CCPA/CPRA, and emerging \
US state privacy laws (VCDPA, CPA, CTDPA, etc.), EU adequacy decisions, and SCCs.
Your task is to extract structured data privacy obligation data from a regulatory filing.
Identify implications for data subject rights, consent mechanisms, lawful processing bases, \
cross-border transfer mechanisms, data retention policies, DPIA triggers, breach notification \
timelines, and fine exposure direction.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "data_subject_rights_changes":   [<string>],
  "consent_framework_changes":     [<string>],
  "lawful_basis_impacts":          [<string>],
  "cross_border_transfer_changes": [<string>],
  "retention_policy_changes":      [<string>],
  "dpia_triggers":                 [<string>],
  "breach_notification_changes":   [<string>],
  "fine_exposure_direction":       "increase" | "decrease" | "neutral" | "unknown",
  "new_obligations":               [<string>],
  "action_items":                  [<string>],
  "confidence":                    <float 0-1>,
  "summary":                       "<concise data privacy obligation summary>"
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


class DataPrivacySkill(Skill):
    metadata = SkillMetadata(
        name="data_privacy_obligation",
        description=(
            "Identify new or changed data privacy obligations from a regulatory filing "
            "— maps GDPR, CCPA, and state privacy law changes to data subject rights, "
            "consent frameworks, cross-border transfer mechanisms, and breach notification "
            "timelines. Actionable for DPOs, privacy engineering, and compliance teams."
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
            "dict — {data_subject_rights_changes, consent_framework_changes, "
            "lawful_basis_impacts, cross_border_transfer_changes, retention_policy_changes, "
            "dpia_triggers, breach_notification_changes, fine_exposure_direction, "
            "new_obligations, action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "privacy",
            "gdpr",
            "ccpa",
            "data-protection",
            "consent",
            "dpo",
            "breach-notification",
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

        raw = context.llm.complete(DATA_PRIVACY_SYSTEM, user_prompt, temperature=0.1)

        fallback = {
            "data_subject_rights_changes": [],
            "consent_framework_changes": [],
            "lawful_basis_impacts": [],
            "cross_border_transfer_changes": [],
            "retention_policy_changes": [],
            "dpia_triggers": [],
            "breach_notification_changes": [],
            "fine_exposure_direction": "unknown",
            "new_obligations": [],
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
                "fine_exposure_direction": parsed.get("fine_exposure_direction"),
            },
        )
