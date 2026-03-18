"""Skill: AI Regulatory Impact Analysis — map EU AI Act risk tier classifications, conformity assessment requirements, FTC AI guidance, and foundation model obligations.

Designed for AI product teams, responsible AI officers, and legal counsel building
compliance workflows around emerging AI governance frameworks. Parses a regulatory
filing for structured AI regulatory implications under EU and US frameworks.
"""

from naturalsentinel.agent_framework import (
    Skill, SkillMetadata, SkillParameter, SkillContext, SkillResult,
    Permission, LatencyClass,
)
from naturalsentinel.fetchers import DOMAIN_BUSINESS_LINES
from naturalsentinel.utils.parsing import parse_llm_json


AI_REGULATORY_SYSTEM = """\
You are a senior AI governance and regulatory specialist with expertise in the EU AI Act \
(AIA), FTC AI fairness guidance, NIST AI Risk Management Framework, and OECD AI Principles.
Your task is to extract structured AI regulatory impact data from a regulatory filing.
Identify implications for risk tier classification, conformity assessment requirements, \
technical documentation obligations, human oversight mandates, transparency disclosures, \
prohibited AI practices, GPAI/foundation model obligations, FTC unfairness risks, and \
audit requirements.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "risk_tier_classification":        "prohibited" | "high_risk" | "limited_risk" | "minimal_risk" | "unknown",
  "conformity_assessment_required":  <bool>,
  "technical_documentation_changes": [<string>],
  "human_oversight_requirements":    [<string>],
  "transparency_obligations":        [<string>],
  "prohibited_practice_implications":[<string>],
  "foundation_model_obligations":    [<string>],
  "ftc_unfairness_risks":            [<string>],
  "audit_requirements":              [<string>],
  "action_items":                    [<string>],
  "confidence":                      <float 0-1>,
  "summary":                         "<concise AI regulatory impact summary>"
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


class AIRegulatorySkill(Skill):
    metadata = SkillMetadata(
        name="ai_regulatory_impact",
        description=(
            "Parse regulatory filings for AI governance obligations — maps EU AI Act risk "
            "tier classifications, conformity assessment requirements, FTC AI guidance, and "
            "foundation model obligations. Actionable for AI product teams, responsible AI "
            "officers, and legal counsel."
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
            "dict — {risk_tier_classification, conformity_assessment_required, "
            "technical_documentation_changes, human_oversight_requirements, "
            "transparency_obligations, prohibited_practice_implications, "
            "foundation_model_obligations, ftc_unfairness_risks, audit_requirements, "
            "action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=["ai", "ai-act", "eu-ai-act", "foundation-model", "risk-classification", "ftc", "algorithmic"],
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

        raw = context.llm.complete(AI_REGULATORY_SYSTEM, user_prompt, temperature=0.1)

        fallback = {
            "risk_tier_classification": "unknown",
            "conformity_assessment_required": False,
            "technical_documentation_changes": [],
            "human_oversight_requirements": [],
            "transparency_obligations": [],
            "prohibited_practice_implications": [],
            "foundation_model_obligations": [],
            "ftc_unfairness_risks": [],
            "audit_requirements": [],
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
                "risk_tier_classification": parsed.get("risk_tier_classification"),
            },
        )
