"""Cross-cutting framework bones for NaturalSentinel.

This package is the single home for framework primitives that every other
subsystem depends on: the ``Skill`` base class and its context, the
``AgentRuntime`` orchestrator, the ``Permission`` flag enum, the
``AuditLog`` sink, and (in Phase P2) decorator-based registries.

Before Phase R, these lived at ``app.naturalsentinel.agent_framework``
(a 700+ line grab-bag). This package replaces that — the legacy module
remains as a deprecation shim until its removal in a future release.

Import from here::

    from app.naturalsentinel.core import (
        AgentRuntime,
        Skill,
        SkillContext,
        SkillResult,
        Permission,
        AuditLog,
    )
"""

from app.naturalsentinel.core.audit import AuditEntry, AuditLog
from app.naturalsentinel.core.permissions import (
    FULL,
    READONLY,
    STANDARD,
    Permission,
    SecurityPolicy,
)
from app.naturalsentinel.core.runtime import AgentRuntime, SkillRegistry
from app.naturalsentinel.core.skill import (
    ExecutionPlan,
    LatencyClass,
    PlanStep,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)

__all__ = [
    "FULL",
    "READONLY",
    "STANDARD",
    "AgentRuntime",
    "AuditEntry",
    "AuditLog",
    "ExecutionPlan",
    "LatencyClass",
    "Permission",
    "PlanStep",
    "SecurityPolicy",
    "Skill",
    "SkillContext",
    "SkillMetadata",
    "SkillParameter",
    "SkillRegistry",
    "SkillResult",
]
