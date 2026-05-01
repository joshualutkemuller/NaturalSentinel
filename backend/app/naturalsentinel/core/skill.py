"""Skill base class, execution context, metadata, and plan primitives.

A Skill is a named, permission-gated capability. Skills declare their
input schema, permissions, and latency class via SkillMetadata, then
override ``execute(context) -> SkillResult``. The runtime constructs
the SkillContext and enforces permissions — skills never create their
own context.

This was previously part of ``app.naturalsentinel.agent_framework``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from app.naturalsentinel.core.permissions import Permission

if TYPE_CHECKING:
    from app.naturalsentinel.core.runtime import AgentRuntime


class LatencyClass(Enum):
    """Expected execution speed."""

    INSTANT = "instant"  # < 100ms — pure computation
    FAST = "fast"  # < 2s — local DB / cached data
    MODERATE = "moderate"  # 2-15s — single LLM call
    SLOW = "slow"  # 15-60s — multiple LLM calls or network
    BATCH = "batch"  # > 60s — full scan cycle


# ═══════════════════════════════════════════════════════════════════════════
# SKILL METADATA
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class SkillParameter:
    """Declared parameter for a skill."""

    name: str
    type: str  # "str", "int", "bool", "list[str]", "dict", etc.
    description: str
    required: bool = True
    default: Any = None


@dataclass
class SkillMetadata:
    """Everything the runtime needs to know about a skill *before* executing it."""

    name: str
    description: str
    version: str  # Semver
    permissions: Permission  # What this skill is allowed to do
    latency: LatencyClass
    parameters: list[SkillParameter]  # Input schema
    returns: str  # Description of output type
    dependencies: list[str] = field(
        default_factory=list
    )  # Other skill names this may call
    max_token_budget: int = 4096  # Soft cap on LLM tokens per invocation
    cacheable: bool = False  # Can results be cached for identical inputs?
    tags: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# SKILL BASE
# ═══════════════════════════════════════════════════════════════════════════


class Skill:
    """
    Base class for all agent skills.

    Subclass this, declare metadata, and implement execute().
    The runtime handles permissions, logging, and error recovery.
    """

    metadata: SkillMetadata

    def execute(self, context: SkillContext) -> SkillResult:
        """
        Run the skill.

        Args:
            context: Provides access to the LLM, memory, parameters, and
                     other skills — but only the ones this skill has
                     permission to use.

        Returns:
            SkillResult with the output data and execution metadata.
        """
        raise NotImplementedError


# ═══════════════════════════════════════════════════════════════════════════
# EXECUTION CONTEXT & RESULTS
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class SkillContext:
    """
    Sandboxed execution environment passed to each skill.

    The runtime constructs this for each invocation, filtering available
    capabilities to match the skill's declared permissions.
    """

    # Parameters the user/planner passed in
    params: dict[str, Any]

    # Gated accessors — only populated if the skill has permission
    llm: Any | None = None  # ModelProvider (LLM_READ or LLM_WRITE)
    memory: Any | None = None  # MemoryStore (MEMORY_READ or MEMORY_WRITE)
    state_path: str | None = None  # Path to state file (STATE_READ or STATE_WRITE)

    # Permission flags so the skill can check at runtime
    permissions: Permission = Permission.NONE

    # Reference to the runtime for invoking sub-skills
    _runtime: AgentRuntime | None = None

    # Execution metadata
    invocation_id: str = ""
    parent_invocation_id: str = ""

    def invoke_skill(self, skill_name: str, params: dict[str, Any]) -> SkillResult:
        """Invoke another skill (if this skill has it as a declared dependency)."""
        if self._runtime is None:
            raise RuntimeError("No runtime attached — cannot invoke sub-skills")
        return self._runtime.execute_skill(
            skill_name, params, parent_invocation_id=self.invocation_id
        )

    def has_permission(self, perm: Permission) -> bool:
        return bool(self.permissions & perm)


@dataclass
class SkillResult:
    """Output from a skill execution."""

    skill_name: str = ""
    success: bool = False
    data: Any = None  # The actual output
    error: str = ""
    invocation_id: str = ""
    duration_ms: float = 0.0
    token_usage: int = 0  # Approximate LLM tokens consumed
    metadata: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════
# EXECUTION PLAN
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class PlanStep:
    """One step in an execution plan."""

    skill_name: str
    params: dict[str, Any]
    depends_on: list[str] = field(
        default_factory=list
    )  # invocation IDs this step waits for
    description: str = ""


@dataclass
class ExecutionPlan:
    """Ordered sequence of skill invocations to achieve a goal."""

    goal: str
    steps: list[PlanStep]
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
