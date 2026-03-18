"""Skill: Assemble a memory context block for LLM prompt injection."""

from naturalsentinel.agent_framework import (
    Skill, SkillMetadata, SkillParameter, SkillContext, SkillResult,
    Permission, LatencyClass,
)


class BuildContextSkill(Skill):
    metadata = SkillMetadata(
        name="build_context",
        description=(
            "Query memory for relevant past analyses, entity knowledge, and "
            "correction precedents, then format them into a context block that "
            "can be injected into an LLM prompt."
        ),
        version="1.0.0",
        permissions=Permission.MEMORY_READ,
        latency=LatencyClass.FAST,
        parameters=[
            SkillParameter("domain", "str", "Regulatory domain code (sec, cfpb, etc.)."),
            SkillParameter("filing_text", "str", "The filing text to find context for."),
            SkillParameter("max_tokens", "int", "Soft cap on context length.", required=False, default=1500),
        ],
        returns="str — formatted memory context block (empty if no relevant memories)",
        dependencies=[],
        cacheable=False,
        tags=["memory", "context", "read-only", "prompt-engineering"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        if context.memory is None:
            return SkillResult(skill_name=self.metadata.name, success=True, data="", metadata={"reason": "no memory attached"})

        block = context.memory.build_context_block(
            context.params["domain"],
            context.params["filing_text"],
            max_tokens=context.params.get("max_tokens", 1500),
        )
        return SkillResult(
            skill_name=self.metadata.name, success=True, data=block,
            metadata={"length": len(block), "has_content": bool(block)},
        )
