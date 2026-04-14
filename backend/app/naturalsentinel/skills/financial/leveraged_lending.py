"""Skill: Leveraged Lending Assessment — CLO risk retention, covenants, underwriting standards.

Assesses regulatory changes to leveraged lending guidelines, CLO risk retention rules,
covenant requirements, and credit underwriting standards. Maps changes to portfolio
thresholds, documentation requirements, and supervisory review triggers. Directly
actionable for Secured Lending and Financing Solutions desks managing leveraged
finance portfolios and CLO structuring.
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

LEVERAGED_LENDING_SYSTEM = """\
You are a senior leveraged finance credit officer with deep expertise in US and EU \
leveraged lending guidelines (OCC/Fed/FDIC 2013 Guidance, ECB Leveraged Finance \
Guidance), CLO risk retention rules (Dodd-Frank Section 15G, EU Securitisation \
Regulation), covenant structures, and credit underwriting standards for leveraged \
buyouts and sponsor-backed transactions.
Given a regulatory filing, extract all structured impacts on leverage thresholds, \
definitions, covenant requirements, CLO risk retention, supervisory review triggers, \
and credit policy requirements.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "leverage_threshold_changes":     [{"metric": <str>, "old_threshold": <str>, "new_threshold": <str>}],
  "definition_changes":             [<string>],
  "covenant_requirement_changes":   [<string>],
  "risk_retention_changes":         [<string>],
  "supervisory_review_triggers":    [<string>],
  "portfolio_classification_impacts": [<string>],
  "documentation_requirements":     [<string>],
  "exception_process_changes":      [<string>],
  "credit_policy_updates_required": [<string>],
  "action_items":                   [<string>],
  "confidence":                     <float 0-1>,
  "summary":                        "<concise leveraged lending impact summary>"
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


class LeveragedLendingSkill(Skill):
    metadata = SkillMetadata(
        name="leveraged_lending_assessment",
        description=(
            "Assess regulatory changes to leveraged lending guidelines, CLO risk "
            "retention rules, covenant requirements, and credit underwriting standards. "
            "Maps changes to specific portfolio thresholds, documentation requirements, "
            "and supervisory review triggers for Secured Lending and Financing Solutions desks."
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
            "dict — {leverage_threshold_changes, definition_changes, "
            "covenant_requirement_changes, risk_retention_changes, "
            "supervisory_review_triggers, portfolio_classification_impacts, "
            "documentation_requirements, exception_process_changes, "
            "credit_policy_updates_required, action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "leveraged-lending",
            "clo",
            "risk-retention",
            "covenants",
            "underwriting",
            "secured-lending",
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
            LEVERAGED_LENDING_SYSTEM, user_prompt, temperature=0.1
        )

        fallback = {
            "leverage_threshold_changes": [],
            "definition_changes": [],
            "covenant_requirement_changes": [],
            "risk_retention_changes": [],
            "supervisory_review_triggers": [],
            "portfolio_classification_impacts": [],
            "documentation_requirements": [],
            "exception_process_changes": [],
            "credit_policy_updates_required": ["Manual review required"],
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
                "domain": domain,
            },
        )
