"""Skill: Regulatory Reporting Analysis — CCAR/DFAST, Form PF, FR Y-14, FINRA, SFTR.

Identifies new or changed regulatory reporting obligations from a filing. Surfaces
schema changes, new data elements, methodology updates, and deadline shifts for
CCAR/DFAST, Form PF, FR Y-14, FINRA reporting, and SFTR. Directly actionable for
data engineering and reporting pipeline teams managing regulatory submissions.
"""

from naturalsentinel.agent_framework import (
    Skill, SkillMetadata, SkillParameter, SkillContext, SkillResult,
    Permission, LatencyClass,
)
from naturalsentinel.fetchers import DOMAIN_BUSINESS_LINES
from naturalsentinel.utils.parsing import parse_llm_json


REGULATORY_REPORTING_SYSTEM = """\
You are a senior regulatory reporting specialist with deep expertise in US and EU \
regulatory submission frameworks including CCAR, DFAST, FR Y-14 (A/C/M/Q schedules), \
Form PF, FINRA reporting obligations, and SFTR (Securities Financing Transactions \
Regulation).
Given a regulatory filing, identify all new or changed reporting obligations, schema \
changes, methodology updates, deadline shifts, and data pipeline implications.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "new_reporting_obligations":      [<string>],
  "changed_reporting_schedules":    [{"form_name": <str>, "change_description": <str>, "effective_date": <str>}],
  "schema_changes":                 [<string>],
  "methodology_updates":            [<string>],
  "system_pipeline_impacts":        [<string>],
  "deadline_changes":               [{"report": <str>, "old_deadline": <str>, "new_deadline": <str>}],
  "data_element_additions":         [<string>],
  "estimated_build_effort":         "low" | "medium" | "high",
  "action_items":                   [<string>],
  "confidence":                     <float 0-1>,
  "summary":                        "<concise regulatory reporting impact summary>"
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


class RegulatoryReportingSkill(Skill):
    metadata = SkillMetadata(
        name="regulatory_reporting_analysis",
        description=(
            "Identify new or changed regulatory reporting obligations from a filing. "
            "Surfaces schema changes, new data elements, methodology updates, and "
            "deadline shifts for CCAR/DFAST, Form PF, FR Y-14, FINRA reporting, and "
            "SFTR — directly actionable for data engineering and reporting pipeline teams."
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
            "dict — {new_reporting_obligations, changed_reporting_schedules, "
            "schema_changes, methodology_updates, system_pipeline_impacts, "
            "deadline_changes, data_element_additions, estimated_build_effort, "
            "action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=["reporting", "ccar", "dfast", "form-pf", "y-14", "pipeline", "data-engineering"],
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

        raw = context.llm.complete(REGULATORY_REPORTING_SYSTEM, user_prompt, temperature=0.1)

        fallback = {
            "new_reporting_obligations": [],
            "changed_reporting_schedules": [],
            "schema_changes": [],
            "methodology_updates": [],
            "system_pipeline_impacts": [],
            "deadline_changes": [],
            "data_element_additions": [],
            "estimated_build_effort": "low",
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
                "estimated_build_effort": parsed.get("estimated_build_effort"),
            },
        )
