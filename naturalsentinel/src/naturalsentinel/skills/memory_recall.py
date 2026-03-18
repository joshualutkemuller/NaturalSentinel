"""Skill: Semantic search across the persistent memory store."""

from naturalsentinel.agent_framework import (
    Skill, SkillMetadata, SkillParameter, SkillContext, SkillResult,
    Permission, LatencyClass,
)


class RecallMemorySkill(Skill):
    metadata = SkillMetadata(
        name="recall_memory",
        description="Search persistent memory for relevant past analyses, entity knowledge, or correction precedents.",
        version="1.0.0",
        permissions=Permission.MEMORY_READ,
        latency=LatencyClass.FAST,
        parameters=[
            SkillParameter("query", "str", "Natural-language search query."),
            SkillParameter("memory_type", "str", "Filter: 'episodic', 'entity', or 'precedent'.", required=False, default=None),
            SkillParameter("top_k", "int", "Max results to return.", required=False, default=5),
        ],
        returns="list[dict] — matching memory records with relevance scores",
        dependencies=[],
        cacheable=False,
        tags=["memory", "search", "read-only"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        if context.memory is None:
            return SkillResult(skill_name=self.metadata.name, success=False, data=None, error="Memory access denied")

        from naturalsentinel.memory.types import MemoryType
        mt = MemoryType(context.params["memory_type"]) if context.params.get("memory_type") else None
        records = context.memory.recall(
            context.params["query"],
            top_k=context.params.get("top_k", 5),
            memory_type=mt,
        )
        return SkillResult(
            skill_name=self.metadata.name, success=True,
            data=[
                {"id": r.id, "type": r.memory_type.value, "key": r.key,
                 "relevance": round(r.relevance_score, 4), "content": r.content}
                for r in records
            ],
            metadata={"count": len(records)},
        )
