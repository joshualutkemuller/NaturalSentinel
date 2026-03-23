"""Skill: Record human feedback that teaches the agent to self-correct."""

from naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)


class RecordFeedbackSkill(Skill):
    metadata = SkillMetadata(
        name="record_feedback",
        description=(
            "Record a human correction on a past analysis. Creates a precedent "
            "memory that future analyses will see, enabling the agent to learn."
        ),
        version="1.0.0",
        permissions=Permission.MEMORY_WRITE | Permission.MEMORY_READ,
        latency=LatencyClass.FAST,
        parameters=[
            SkillParameter("filing_id", "str", "The filing ID to correct."),
            SkillParameter(
                "field", "str", "Which field to correct (severity, affected_business_lines, etc.)."
            ),
            SkillParameter("old_value", "str", "The current/wrong value."),
            SkillParameter("new_value", "str", "The correct value."),
            SkillParameter(
                "reason", "str", "Why this correction is needed.", required=False, default=""
            ),
        ],
        returns="dict — confirmation",
        dependencies=[],
        tags=["feedback", "learning", "memory", "write"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        if context.memory is None:
            return SkillResult(
                skill_name=self.metadata.name,
                success=False,
                data=None,
                error="Memory access denied",
            )

        p = context.params
        context.memory.record_feedback(
            p["filing_id"], p["field"], p["old_value"], p["new_value"], p.get("reason", "")
        )
        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data={"recorded": f"{p['filing_id']}.{p['field']}", "new_value": p["new_value"]},
        )
