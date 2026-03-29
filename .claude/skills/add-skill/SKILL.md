---
description: Scaffold a new NaturalSentinel agent Skill subclass with correct Permission flags, wire it into ALL_SKILLS, and add a unit test.
context: fork
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Scaffold a new NaturalSentinel agent skill.

Skill class name and description: $ARGUMENTS
(e.g., `DeadlineEscalationSkill — escalate filings with compliance deadlines within 30 days`)

## Step 1 — Read the framework

Read `backend/app/naturalsentinel/agent_framework.py` lines 1–120 to understand `Skill`, `SkillMetadata`, `SkillContext`, `SkillResult`, `Permission`, and `LatencyClass`.

Also read `backend/app/naturalsentinel/skills/__init__.py` to see the `ALL_SKILLS` list.

## Step 2 — Create the skill file

Create `backend/app/naturalsentinel/skills/<snake_name>.py`:

```python
"""<Description>."""

from __future__ import annotations

from app.naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillResult,
)


class <ClassName>(Skill):
    metadata = SkillMetadata(
        name="<snake_name>",
        description="<one-line description>",
        permissions=Permission.LLM_READ | Permission.MEMORY_READ,  # narrowest set
        latency=LatencyClass.MODERATE,
        parameters=[
            # {"name": "filing_id", "type": "str", "required": True, "description": "..."},
        ],
        tags=["<group>"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        params = context.params
        try:
            # context.llm — only if LLM_READ or LLM_WRITE declared
            # context.memory — only if MEMORY_READ or MEMORY_WRITE declared
            ...
            return SkillResult(skill_name=self.metadata.name, success=True, data={...})
        except Exception as exc:
            return SkillResult(skill_name=self.metadata.name, success=False, error=str(exc))
```

**Permission flags:** `LLM_READ`, `LLM_WRITE`, `MEMORY_READ`, `MEMORY_WRITE`, `STATE_READ`, `STATE_WRITE`, `FETCH_LOCAL`, `FETCH_NETWORK`, `FILE_READ`, `FILE_WRITE`, `HUMAN_INPUT`

Declare the **narrowest set** actually used — no speculative permissions.

**Latency:** `instant` (<100ms) · `fast` (<2s) · `moderate` (2–15s) · `slow` (15–60s) · `batch` (>60s)

## Step 3 — Register in ALL_SKILLS

Edit `backend/app/naturalsentinel/skills/__init__.py`:
```python
from app.naturalsentinel.skills.<snake_name> import <ClassName>

ALL_SKILLS = [
    ...,
    <ClassName>,
]
```

## Step 4 — Verify API access

Read `backend/app/api/deps.py` — confirm `get_ns_runtime` registers `ALL_SKILLS`. If it doesn't, the new skill won't be accessible via the API's `NsRuntimeDep`.

## Step 5 — Unit test

Create `backend/tests/naturalsentinel/skills/test_<snake_name>.py`:
- Instantiate directly, pass a `SkillContext` with `MockProvider`
- Assert `result.success is True` and expected keys in `result.data`
- Test failure path: bad params → `result.success is False`
