"""Skill: Check filings against deduplication state."""

import json
from pathlib import Path

from naturalsentinel.agent_framework import (
    Skill, SkillMetadata, SkillParameter, SkillContext, SkillResult,
    Permission, LatencyClass,
)


class DetectDuplicatesSkill(Skill):
    metadata = SkillMetadata(
        name="detect_duplicates",
        description=(
            "Filter a list of filings against previously-seen IDs stored in "
            "the state file. Returns only new (unseen) filings and optionally "
            "updates the state."
        ),
        version="1.0.0",
        permissions=Permission.STATE_READ | Permission.STATE_WRITE,
        latency=LatencyClass.INSTANT,
        parameters=[
            SkillParameter("filings", "list[dict]", "List of serialized filings to check."),
            SkillParameter("mark_seen", "bool", "Whether to update state with the new IDs.", required=False, default=True),
        ],
        returns="dict — {new_filings: list[dict], duplicates_skipped: int}",
        dependencies=[],
        cacheable=False,
        tags=["dedup", "state", "filtering"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        filings = context.params["filings"]
        mark_seen = context.params.get("mark_seen", True)

        # Load seen IDs
        seen: set[str] = set()
        state_path = Path(context.state_path) if context.state_path else None
        if state_path and state_path.exists() and context.has_permission(Permission.STATE_READ):
            try:
                data = json.loads(state_path.read_text())
                seen = set(data.get("seen_ids", []))
            except (json.JSONDecodeError, OSError):
                pass

        new = [f for f in filings if f.get("id") not in seen]
        skipped = len(filings) - len(new)

        # Update state
        if mark_seen and state_path and context.has_permission(Permission.STATE_WRITE):
            seen.update(f.get("id") for f in new if f.get("id"))
            state_path.write_text(json.dumps({"seen_ids": sorted(seen)}))

        return SkillResult(
            skill_name=self.metadata.name, success=True,
            data={"new_filings": new, "duplicates_skipped": skipped},
            metadata={"total_input": len(filings), "new_count": len(new)},
        )
