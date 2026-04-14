"""Cross-cutting framework bones for NaturalSentinel.

This package is the single home for framework primitives that every other
subsystem depends on: the ``Skill`` base class and its context, the
``AgentRuntime`` orchestrator, the ``Permission`` flag enum, the
``AuditLog`` sink, decorator-based registries, and framework-wide
constants.

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
        register_skill,
    )
"""
