"""Skill: Generate an executive regulatory briefing from stored analyses."""

from naturalsentinel.agent_framework import (
    Skill, SkillMetadata, SkillParameter, SkillContext, SkillResult,
    Permission, LatencyClass,
)


BRIEFING_SYSTEM = """\
You are a regulatory intelligence analyst preparing an executive briefing.
Write in clear, direct prose. No filler. Lead with what matters most.
Format as structured markdown with sections for Critical Items, Upcoming \
Deadlines, and Recommended Actions by Department.
Respond ONLY with the briefing content — no preamble.
"""

BRIEFING_USER = """\
Produce a concise regulatory briefing for {audience}.

Recent regulatory changes analyzed:
{filing_summaries}

Requirements:
1. Executive summary (3-4 sentences)
2. Critical items requiring immediate attention
3. Upcoming compliance deadlines (sorted by urgency)
4. Recommended actions organized by department
"""


class GenerateBriefingSkill(Skill):
    metadata = SkillMetadata(
        name="generate_briefing",
        description=(
            "Produce an executive-level regulatory briefing by reading recent "
            "analyses from memory and synthesizing them through the LLM."
        ),
        version="1.0.0",
        permissions=Permission.LLM_READ | Permission.MEMORY_READ,
        latency=LatencyClass.MODERATE,
        parameters=[
            SkillParameter("audience", "str", "Target audience (e.g. 'board', 'compliance_team', 'general_counsel').", required=False, default="executive leadership"),
            SkillParameter("limit", "int", "Max number of recent analyses to include.", required=False, default=10),
        ],
        returns="str — formatted briefing text",
        dependencies=["recall_memory"],
        max_token_budget=8192,
        tags=["output", "llm", "briefing", "synthesis"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        if context.llm is None:
            return SkillResult(skill_name=self.metadata.name, success=False, data=None, error="LLM access denied")
        if context.memory is None:
            return SkillResult(skill_name=self.metadata.name, success=False, data=None, error="Memory access denied")

        audience = context.params.get("audience", "executive leadership")
        limit = context.params.get("limit", 10)

        records = context.memory.get_filing_history(limit=limit)
        if not records:
            return SkillResult(
                skill_name=self.metadata.name, success=True,
                data="No analyses in memory. Run a scan cycle first.",
                metadata={"filings_used": 0},
            )

        lines = []
        for rec in records:
            f = rec.content.get("filing", {})
            i = rec.content.get("impact", {})
            deadline = i.get("compliance_deadline", "none")
            lines.append(
                f"- [{i.get('severity', '?').upper()}] {f.get('title', '?')} "
                f"({f.get('domain', '?').upper()}, {f.get('change_type', '?')}) "
                f"deadline={deadline}, actions={len(i.get('action_items', []))}"
            )

        prompt = BRIEFING_USER.format(audience=audience, filing_summaries="\n".join(lines))
        raw = context.llm.complete(BRIEFING_SYSTEM, prompt, temperature=0.3)

        return SkillResult(
            skill_name=self.metadata.name, success=True, data=raw,
            token_usage=len(prompt) // 4 + len(raw) // 4,
            metadata={"filings_used": len(records), "audience": audience},
        )
