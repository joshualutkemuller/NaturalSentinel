"""Skill: Execute a step-by-step document review process."""

from app.naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)


class FollowProcessSkill(Skill):
    metadata = SkillMetadata(
        name="follow_process",
        description=(
            "Execute a registered document review process step by step. Each call "
            "advances the process by one step, retrieves relevant document context for "
            "that step, and returns instructions + context + progress tracking. "
            "Sessions persist so processes can be paused and resumed. Use action='start' "
            "to begin, 'next' to advance with findings, 'skip' to skip a step, "
            "'status' to inspect state, or 'complete' to close the session."
        ),
        version="1.0.0",
        permissions=(
            Permission.MEMORY_READ | Permission.MEMORY_WRITE | Permission.FILE_WRITE
        ),
        latency=LatencyClass.MODERATE,
        parameters=[
            SkillParameter(
                "process_name",
                "str",
                "Registered process definition name.",
                required=True,
            ),
            SkillParameter(
                "doc_ids", "list[str]", "Documents to review.", required=True
            ),
            SkillParameter(
                "session_id",
                "str",
                "Resume existing session. Omit to start new.",
                required=False,
                default="",
            ),
            SkillParameter(
                "action",
                "str",
                "One of: start, next, skip, status, complete.",
                required=False,
                default="start",
            ),
            SkillParameter(
                "step_result",
                "dict",
                "Findings for the just-completed step: {findings: str, status: pass|fail|flagged|skipped}.",
                required=False,
                default={},
            ),
        ],
        returns="dict — session_id, current_step (with context), progress",
        dependencies=["recall_context"],
        max_token_budget=4096,
        cacheable=False,
        tags=["document", "process", "review"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        from app.naturalsentinel.documents.process_engine import follow_process

        process_name = context.params.get("process_name", "")
        doc_ids = context.params.get("doc_ids", [])
        if not process_name or not doc_ids:
            return SkillResult(
                success=False, error="'process_name' and 'doc_ids' are required"
            )

        ov_client = (
            getattr(context, "extras", {}).get("ov_client")
            if hasattr(context, "extras")
            else None
        )
        qdrant_client = (
            getattr(context, "extras", {}).get("qdrant_client")
            if hasattr(context, "extras")
            else None
        )
        session_db = (
            getattr(context, "extras", {}).get("session_db")
            if hasattr(context, "extras")
            else None
        )

        session_id = context.params.get("session_id") or None
        action = context.params.get("action", "start")
        step_result = context.params.get("step_result") or None

        result = follow_process(
            process_name=process_name,
            doc_ids=doc_ids,
            session_id=session_id,
            action=action,
            step_result=step_result,
            ov_client=ov_client,
            qdrant_client=qdrant_client,
            session_db=session_db,
        )

        if "error" in result:
            return SkillResult(success=False, error=result["error"])
        return SkillResult(success=True, data=result)
