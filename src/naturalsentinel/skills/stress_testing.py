"""Skill: Stress Testing Signal — CCAR/DFAST scenario parameters and desk P&L mapping.

Extracts stress scenario parameters from regulatory filings and maps them to
desk-level P&L impacts. Parses CCAR/DFAST supervisory scenarios, Fed exploratory
shocks, and EBA stress scenarios to identify macro variable paths, securities
financing stresses, and hedging implications. Directly actionable for stress
testing teams and capital planning groups.
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

STRESS_TESTING_SYSTEM = """\
You are a senior stress testing quant and capital planning analyst with deep expertise \
in CCAR (Comprehensive Capital Analysis and Review), DFAST (Dodd-Frank Act Stress \
Testing), Fed exploratory shock scenarios, and EBA EU-wide stress test methodologies.
Given a regulatory filing, extract all structured stress scenario parameters including \
macro variable paths (baseline, adverse, severely adverse), securities financing \
stresses, desk-level P&L drivers, hedging implications, and capital adequacy impacts.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "scenario_type":                  "supervisory" | "exploratory" | "internal" | "unknown",
  "macro_variables":                [{"variable": <str>, "baseline": <str>, "adverse": <str>, "severely_adverse": <str>}],
  "securities_financing_stress":    [{"market": <str>, "stress_description": <str>, "magnitude": <str>}],
  "desk_pl_drivers":                [{"desk": <str>, "driver": <str>, "estimated_impact_direction": "positive" | "negative" | "neutral" | "unknown"}],
  "hedging_implications":           [<string>],
  "capital_adequacy_impacts":       [<string>],
  "model_update_requirements":      [<string>],
  "submission_deadline":            <str | null>,
  "action_items":                   [<string>],
  "confidence":                     <float 0-1>,
  "summary":                        "<concise stress testing impact summary>"
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


class StressTestingSignalSkill(Skill):
    metadata = SkillMetadata(
        name="stress_testing_signal",
        description=(
            "Extract stress scenario parameters and map them to desk-level P&L impacts. "
            "Parses CCAR/DFAST supervisory scenarios, Fed exploratory shocks, and EBA "
            "stress scenarios to identify macro variable paths, securities financing "
            "stresses, and hedging implications — directly actionable for stress testing "
            "teams and capital planning."
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
            "dict — {scenario_type, macro_variables, securities_financing_stress, "
            "desk_pl_drivers, hedging_implications, capital_adequacy_impacts, "
            "model_update_requirements, submission_deadline, action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "stress-testing",
            "ccar",
            "dfast",
            "scenario",
            "macro",
            "pl-impact",
            "capital-planning",
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

        raw = context.llm.complete(STRESS_TESTING_SYSTEM, user_prompt, temperature=0.1)

        fallback = {
            "scenario_type": "unknown",
            "macro_variables": [],
            "securities_financing_stress": [],
            "desk_pl_drivers": [],
            "hedging_implications": [],
            "capital_adequacy_impacts": [],
            "model_update_requirements": [],
            "submission_deadline": None,
            "action_items": ["Manual review of stress scenarios required"],
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
                "scenario_type": parsed.get("scenario_type"),
            },
        )
