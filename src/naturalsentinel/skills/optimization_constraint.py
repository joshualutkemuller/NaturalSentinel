"""Skill: Optimization Constraint Analysis — formal constraint extraction for quant models.

Translates a regulatory filing into formal optimization model constraints and objective
function modifications. Converts regulatory language into constraint notation usable in
balance sheet optimizers, capital allocation models, and portfolio construction
frameworks. Output includes constraint type, mathematical expression, and affected
portfolios — the most data-science-specific skill in the NaturalSentinel suite.
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

OPTIMIZATION_CONSTRAINT_SYSTEM = """\
You are a senior quantitative analyst and optimization modeller with deep expertise \
in balance sheet optimisation, capital allocation models, and portfolio construction \
frameworks used by major financial institutions.
Your task is to translate regulatory changes from a filing into formal mathematical \
constraints and objective function modifications suitable for use in portfolio \
optimisation solvers (linear programming, convex optimisation, MILP).
Express constraints in plain mathematical notation (e.g. "sum(RWA_i) <= 0.85 * TotalAssets"). \
Identify whether each constraint is hard (must be satisfied), soft (penalised in objective), \
or an objective function modification.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "constraint_type":                "hard" | "soft" | "objective" | "mixed" | "unknown",
  "constraint_expressions":         [{"name": <str>, "expression_text": <str>, "constraint_direction": "<=" | ">=" | "=", "binding_scenario": <str>, "affected_model_types": [<str>]}],
  "objective_function_impacts":     [{"term": <str>, "direction": "increase" | "decrease" | "neutral", "magnitude_estimate": <str>}],
  "portfolio_impacts":              [{"portfolio_name": <str>, "impact_description": <str>}],
  "parameter_updates":              [{"parameter": <str>, "old_value": <str>, "new_value": <str>, "effective_date": <str>}],
  "model_types_affected":           [<string>],
  "recalibration_urgency":          "immediate" | "30-day" | "90-day" | "annual",
  "action_items":                   [<string>],
  "confidence":                     <float 0-1>,
  "summary":                        "<concise optimization constraint impact summary>"
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


class OptimizationConstraintSkill(Skill):
    metadata = SkillMetadata(
        name="optimization_constraint",
        description=(
            "Translate a regulatory filing into formal optimization model constraints "
            "and objective function modifications. The most data-science-specific skill "
            "— converts regulatory language into constraint notation usable in balance "
            "sheet optimizers, capital allocation models, and portfolio construction "
            "frameworks. Output includes constraint type, mathematical expression, and "
            "affected portfolios."
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
            "dict — {constraint_type, constraint_expressions, objective_function_impacts, "
            "portfolio_impacts, parameter_updates, model_types_affected, "
            "recalibration_urgency, action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "optimization",
            "constraints",
            "capital-allocation",
            "balance-sheet",
            "data-science",
            "quant",
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

        raw = context.llm.complete(OPTIMIZATION_CONSTRAINT_SYSTEM, user_prompt, temperature=0.1)

        fallback = {
            "constraint_type": "unknown",
            "constraint_expressions": [],
            "objective_function_impacts": [],
            "portfolio_impacts": [],
            "parameter_updates": [],
            "model_types_affected": [],
            "recalibration_urgency": "90-day",
            "action_items": ["Manual review of optimization models required"],
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
                "recalibration_urgency": parsed.get("recalibration_urgency"),
            },
        )
