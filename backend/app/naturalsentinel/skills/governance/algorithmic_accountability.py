"""Skill: Algorithmic Accountability — identify algorithmic accountability and automated decision-making obligations from regulatory filings.

Designed for AI/ML teams, product counsel, and responsible AI officers. Parses a
regulatory filing for structured algorithmic accountability obligations including bias
audit requirements, explainability mandates, impact assessment triggers, prohibited
inference categories, and opt-out rights.
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

ALGORITHMIC_ACCOUNTABILITY_SYSTEM = """\
You are a senior algorithmic accountability and automated decision-making regulatory \
specialist with expertise in EU AI Act high-risk system requirements, NYC Local Law 144 \
(automated employment decisions), Illinois AEIA, FTC algorithmic fairness guidance, \
and CFPB adverse action notice requirements for ML models.
Your task is to extract structured algorithmic accountability obligation data from a \
regulatory filing.
Identify implications for third-party audit requirement triggers, bias assessment \
obligations, explainability or interpretability mandates, algorithmic impact assessment \
triggers, prohibited sensitive attribute inferences, restrictions on fully automated \
decisions, human review or opt-out right changes, documentation and logging \
requirements, and whether a third-party auditor is required.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "audit_requirement_triggers":       [<string>],
  "bias_assessment_obligations":      [<string>],
  "explainability_requirements":      [<string>],
  "impact_assessment_triggers":       [<string>],
  "prohibited_inferences":            [<string>],
  "automated_decision_restrictions":  [<string>],
  "opt_out_rights_changes":           [<string>],
  "record_keeping_obligations":       [<string>],
  "third_party_auditor_required":     <bool>,
  "action_items":                     [<string>],
  "confidence":                       <float 0-1>,
  "summary":                          "<concise summary>"
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


class AlgorithmicAccountabilitySkill(Skill):
    metadata = SkillMetadata(
        name="algorithmic_accountability",
        description=(
            "Identify algorithmic accountability and automated decision-making "
            "obligations from regulatory filings — maps bias audit requirements, "
            "explainability mandates, impact assessment triggers, prohibited inference "
            "categories, and opt-out rights. Actionable for AI/ML teams, product "
            "counsel, and responsible AI officers."
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
            "dict — {audit_requirement_triggers, bias_assessment_obligations, "
            "explainability_requirements, impact_assessment_triggers, "
            "prohibited_inferences, automated_decision_restrictions, "
            "opt_out_rights_changes, record_keeping_obligations, "
            "third_party_auditor_required, action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "algorithmic",
            "bias-audit",
            "explainability",
            "aia",
            "automated-decision",
            "fairness",
            "impact-assessment",
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
            ALGORITHMIC_ACCOUNTABILITY_SYSTEM, user_prompt, temperature=0.1
        )

        fallback = {
            "audit_requirement_triggers": [],
            "bias_assessment_obligations": [],
            "explainability_requirements": [],
            "impact_assessment_triggers": [],
            "prohibited_inferences": [],
            "automated_decision_restrictions": [],
            "opt_out_rights_changes": [],
            "record_keeping_obligations": [],
            "third_party_auditor_required": False,
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
                "third_party_auditor_required": parsed.get(
                    "third_party_auditor_required"
                ),
            },
        )
