"""Skill: Tech Merger Review — assess regulatory signals relevant to technology and telecom M&A.

Designed for M&A counsel, corporate development, and regulatory affairs teams. Parses
a regulatory filing for structured merger review signals including changes to merger
notification thresholds, theories of harm, FCC license transfer requirements, and
CFIUS foreign investment review triggers.
"""

from naturalsentinel.agent_framework import (
    Skill, SkillMetadata, SkillParameter, SkillContext, SkillResult,
    Permission, LatencyClass,
)
from naturalsentinel.fetchers import DOMAIN_BUSINESS_LINES
from naturalsentinel.utils.parsing import parse_llm_json


TECH_MERGER_REVIEW_SYSTEM = """\
You are a senior technology and telecom M&A antitrust specialist with expertise in \
HSR Act notification thresholds, FTC/DOJ digital market merger review, EU Merger \
Regulation, FCC license transfer proceedings, and CFIUS national security review.
Your task is to extract structured merger review signal data from a regulatory filing.
Identify implications for HSR or EU merger notification threshold triggers, likely \
theories of harm, the likelihood of behavioural or structural remedies, relevant \
market definition changes, Digital Markets Act interface with merger review, FCC \
spectrum and broadcast license transfer obligations, CFIUS or equivalent foreign \
investment review triggers, and HSR waiting period or review timeline changes.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "notification_threshold_triggered":  <bool>,
  "theory_of_harm":                    [<string>],
  "behavioral_remedy_likelihood":      "high" | "medium" | "low" | "unknown",
  "structural_remedy_likelihood":      "high" | "medium" | "low" | "unknown",
  "market_definition_changes":         [<string>],
  "digital_market_act_interface":      [<string>],
  "fcc_license_transfer_requirements": [<string>],
  "foreign_investment_review_triggers":[<string>],
  "review_timeline_changes":           [<string>],
  "action_items":                      [<string>],
  "confidence":                        <float 0-1>,
  "summary":                           "<concise summary>"
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


class TechMergerReviewSkill(Skill):
    metadata = SkillMetadata(
        name="tech_merger_review",
        description=(
            "Assess regulatory signals relevant to technology and telecom M&A — maps "
            "changes to merger notification thresholds, theories of harm (data "
            "accumulation, vertical foreclosure, killer acquisitions), FCC license "
            "transfer requirements, and CFIUS foreign investment review triggers. "
            "Actionable for M&A counsel, corporate development, and regulatory affairs."
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
            "dict — {notification_threshold_triggered, theory_of_harm, "
            "behavioral_remedy_likelihood, structural_remedy_likelihood, "
            "market_definition_changes, digital_market_act_interface, "
            "fcc_license_transfer_requirements, foreign_investment_review_triggers, "
            "review_timeline_changes, action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=["merger", "ma", "antitrust", "hsr", "fcc-transfer", "cfius", "doj", "ftc", "eu-merger"],
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

        raw = context.llm.complete(TECH_MERGER_REVIEW_SYSTEM, user_prompt, temperature=0.1)

        fallback = {
            "notification_threshold_triggered": False,
            "theory_of_harm": [],
            "behavioral_remedy_likelihood": "unknown",
            "structural_remedy_likelihood": "unknown",
            "market_definition_changes": [],
            "digital_market_act_interface": [],
            "fcc_license_transfer_requirements": [],
            "foreign_investment_review_triggers": [],
            "review_timeline_changes": [],
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
                "notification_threshold_triggered": parsed.get("notification_threshold_triggered"),
            },
        )
