"""DEPRECATED — use ``app.naturalsentinel.core`` instead.

This module used to contain the full skill framework (Permission, Skill,
SkillContext, AuditLog, AgentRuntime, etc.) as a 700-line grab-bag.
Phase R split it into focused modules under ``app.naturalsentinel.core``:

    core/permissions.py  — Permission flags + SecurityPolicy
    core/skill.py        — Skill base, SkillContext, SkillResult, LatencyClass,
                           SkillMetadata, SkillParameter, PlanStep, ExecutionPlan
    core/audit.py        — AuditEntry, AuditLog
    core/runtime.py      — SkillRegistry, AgentRuntime

This shim re-exports every public name so legacy imports keep working.
It emits a DeprecationWarning at import time. New code should import
from ``app.naturalsentinel.core`` directly. This shim will be removed
in a future release.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "app.naturalsentinel.agent_framework is deprecated; "
    "import from app.naturalsentinel.core instead. "
    "This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything the old module defined.
from app.naturalsentinel.core.audit import AuditEntry, AuditLog  # noqa: E402,F401
from app.naturalsentinel.core.permissions import (  # noqa: E402,F401
    FULL,
    READONLY,
    STANDARD,
    Permission,
    SecurityPolicy,
)
from app.naturalsentinel.core.runtime import (  # noqa: E402,F401
    AgentRuntime,
    SkillRegistry,
)
from app.naturalsentinel.core.skill import (  # noqa: E402,F401
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
