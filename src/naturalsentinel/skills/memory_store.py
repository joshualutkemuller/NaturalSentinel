"""Skill: Store a filing analysis in persistent episodic memory."""

from naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)


class StoreMemorySkill(Skill):
    metadata = SkillMetadata(
        name="store_memory",
        description="Persist a filing + impact assessment as episodic memory. Auto-extracts entity relations.",
        version="1.0.0",
        permissions=Permission.MEMORY_WRITE,
        latency=LatencyClass.FAST,
        parameters=[
            SkillParameter("filing_id", "str", "Unique filing identifier."),
            SkillParameter("filing", "dict", "Serialized filing data."),
            SkillParameter("impact", "dict", "Impact assessment data."),
        ],
        returns="dict — confirmation with memory stats",
        dependencies=[],
        tags=["memory", "write", "persistence"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        if context.memory is None:
            return SkillResult(
                skill_name=self.metadata.name, success=False, data=None, error="Memory write denied"
            )

        context.memory.store_episodic(
            context.params["filing_id"],
            context.params["filing"],
            context.params["impact"],
        )
        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data={"stored": context.params["filing_id"], "total_memories": context.memory.count()},
        )
