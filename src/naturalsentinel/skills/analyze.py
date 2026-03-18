"""Skill: Analyze a single filing with LLM-powered impact assessment."""

from naturalsentinel.agent_framework import (
    Skill, SkillMetadata, SkillParameter, SkillContext, SkillResult,
    Permission, LatencyClass,
)
from naturalsentinel.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from naturalsentinel.fetchers import DOMAIN_BUSINESS_LINES
from naturalsentinel.utils.parsing import parse_llm_json


class AnalyzeFilingSkill(Skill):
    metadata = SkillMetadata(
        name="analyze_filing",
        description=(
            "Send a single regulatory filing to the LLM for structured impact "
            "analysis. Returns severity, affected business lines, compliance "
            "deadlines, action items, and confidence score. Optionally enriches "
            "the prompt with memory context if the build_context skill provides it."
        ),
        version="1.0.0",
        permissions=Permission.LLM_READ | Permission.LLM_WRITE,
        latency=LatencyClass.MODERATE,
        parameters=[
            SkillParameter("filing", "dict", "Serialized RegulatoryFiling with id, title, domain, raw_text, etc."),
            SkillParameter("memory_context", "str", "Pre-built memory context block to append to the prompt.", required=False, default=""),
        ],
        returns="dict — parsed impact assessment with severity, action_items, etc.",
        dependencies=["build_context"],
        max_token_budget=4096,
        cacheable=False,   # Each analysis should be fresh (model may vary)
        tags=["analysis", "llm", "core"],
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

        user_prompt = USER_PROMPT_TEMPLATE.format(
            filing_id=filing.get("id", "UNKNOWN"),
            domain=domain.upper(),
            title=filing.get("title", ""),
            published_date=filing.get("published_date", ""),
            source_url=filing.get("source_url", ""),
            raw_text=filing.get("raw_text", ""),
            business_lines=", ".join(domain_lines),
        )
        if memory_context:
            user_prompt += "\n" + memory_context

        raw = context.llm.complete(SYSTEM_PROMPT, user_prompt, temperature=0.1)

        fallback = {
            "summary": raw[:500],
            "severity": "medium",
            "affected_business_lines": domain_lines,
            "affected_regulations": [],
            "compliance_deadline": None,
            "action_items": ["Manual review required — model output was unstructured"],
            "risk_summary": "Unable to parse structured assessment.",
            "confidence": 0.3,
        }
        parsed = parse_llm_json(raw, fallback=fallback)

        # Enrich with filing metadata
        parsed["filing_id"] = filing.get("id", "UNKNOWN")
        parsed["domain"] = domain

        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data=parsed,
            token_usage=len(user_prompt) // 4 + len(raw) // 4,
            metadata={"filing_id": filing.get("id"), "severity": parsed.get("severity")},
        )
