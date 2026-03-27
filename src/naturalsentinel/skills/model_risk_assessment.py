"""Skill: Model Risk Assessment — identify SR 11-7 re-validation obligations.

Maps regulatory filing requirements to specific internal quantitative model types
(optimization, ML, pricing, risk) and surfaces re-validation tiers, documentation
gaps, and governance actions. Designed for data science and model risk teams
operating under SR 11-7 / SS1/23 frameworks.
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

MODEL_RISK_SYSTEM = """\
You are a senior model risk officer with deep expertise in SR 11-7 (US) and \
SS1/23 (UK) model risk management frameworks.
Given a regulatory filing, identify which internal quantitative model types \
require re-validation, documentation updates, or governance actions.
Model types in scope include: credit risk models, market risk / VaR / ES models, \
liquidity models, ML / AI scoring models, XVA pricing models, optimisation models, \
stress-testing / DFAST / CCAR models, and AML / surveillance models.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "models_requiring_revalidation":  [<string — model type or name>],
  "validation_tier":                1 | 2 | 3,
  "documentation_updates_required": [<string>],
  "challenger_model_required":      <bool>,
  "drift_monitoring_required":      <bool>,
  "retraining_triggers":            [<string>],
  "governance_actions":             [<string>],
  "examiner_readiness_gaps":        [<string>],
  "urgency":                        "immediate" | "30-day" | "90-day" | "annual",
  "confidence":                     <float 0-1>,
  "summary":                        "<concise model risk impact summary>"
}
"""

_USER_TEMPLATE = """\
FILING ID:      {filing_id}
DOMAIN:         {domain}
TITLE:          {title}
PUBLISHED DATE: {published_date}
SOURCE URL:     {source_url}
BUSINESS LINES: {business_lines}
MODEL INVENTORY: {model_inventory}

FILING TEXT:
{raw_text}
{memory_block}\
"""


class ModelRiskAssessmentSkill(Skill):
    metadata = SkillMetadata(
        name="model_risk_assessment",
        description=(
            "Identify which internal quantitative models require re-validation or "
            "documentation updates based on a regulatory filing. Maps SR 11-7 "
            "obligations to specific model types — optimization, ML, pricing, risk — "
            "used by the data science team."
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
            SkillParameter(
                "model_inventory",
                "list[str]",
                "List of model names/types in scope for this assessment.",
                required=False,
                default=[],
            ),
        ],
        returns=(
            "dict — {models_requiring_revalidation, validation_tier, "
            "documentation_updates_required, challenger_model_required, "
            "drift_monitoring_required, retraining_triggers, governance_actions, "
            "examiner_readiness_gaps, urgency, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "model-risk",
            "sr11-7",
            "validation",
            "ml",
            "optimization",
            "data-science",
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
        model_inventory = context.params.get("model_inventory", [])
        domain = filing.get("domain", "")
        domain_lines = DOMAIN_BUSINESS_LINES.get(domain, [])

        memory_block = ("\n" + memory_context) if memory_context else ""
        inventory_str = (
            ", ".join(model_inventory) if model_inventory else "Not specified"
        )

        user_prompt = _USER_TEMPLATE.format(
            filing_id=filing.get("id", "UNKNOWN"),
            domain=domain.upper(),
            title=filing.get("title", ""),
            published_date=filing.get("published_date", ""),
            source_url=filing.get("source_url", ""),
            raw_text=filing.get("raw_text", ""),
            business_lines=", ".join(domain_lines),
            model_inventory=inventory_str,
            memory_block=memory_block,
        )

        raw = context.llm.complete(MODEL_RISK_SYSTEM, user_prompt, temperature=0.1)

        fallback = {
            "models_requiring_revalidation": [],
            "validation_tier": 2,
            "documentation_updates_required": [],
            "challenger_model_required": False,
            "drift_monitoring_required": False,
            "retraining_triggers": [],
            "governance_actions": ["Manual review of model inventory required"],
            "examiner_readiness_gaps": [],
            "urgency": "90-day",
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
                "urgency": parsed.get("urgency"),
            },
        )
