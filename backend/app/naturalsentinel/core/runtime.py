"""Agent runtime: skill registry + orchestrator.

``SkillRegistry`` holds registered skills and validates their dependency
declarations at registration time. ``AgentRuntime`` owns the registry,
security policy, audit log, and shared resources (LLM provider, memory
store), and executes skills in a sandboxed context with permission
enforcement, parameter validation, result caching, and plan execution.

This was previously part of ``app.naturalsentinel.agent_framework``.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any

from app.naturalsentinel.core.audit import AuditEntry, AuditLog
from app.naturalsentinel.core.permissions import Permission, SecurityPolicy
from app.naturalsentinel.core.skill import (
    ExecutionPlan,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillResult,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# SKILL REGISTRY
# ═══════════════════════════════════════════════════════════════════════════


class SkillRegistry:
    """Typed catalog of available skills with lookup and validation."""

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill):
        """Register a skill. Validates metadata on registration."""
        meta = skill.metadata
        if not meta.name:
            raise ValueError("Skill must have a name")
        if meta.name in self._skills:
            logger.warning("Overwriting existing skill: %s", meta.name)
        self._skills[meta.name] = skill
        logger.debug(
            "Registered skill: %s v%s [%s]", meta.name, meta.version, meta.permissions
        )

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_skills(self) -> list[SkillMetadata]:
        return [s.metadata for s in self._skills.values()]

    def find_by_tag(self, tag: str) -> list[SkillMetadata]:
        return [s.metadata for s in self._skills.values() if tag in s.metadata.tags]

    def find_by_permission(self, perm: Permission) -> list[SkillMetadata]:
        """Find all skills that require a specific permission."""
        return [
            s.metadata for s in self._skills.values() if s.metadata.permissions & perm
        ]

    def dependency_graph(self) -> dict[str, list[str]]:
        """Return {skill_name: [dependency_names]} for all registered skills."""
        return {name: s.metadata.dependencies for name, s in self._skills.items()}

    def validate_dependencies(self) -> list[str]:
        """Return list of missing dependency references."""
        errors = []
        for name, skill in self._skills.items():
            for dep in skill.metadata.dependencies:
                if dep not in self._skills:
                    errors.append(f"{name} depends on '{dep}' which is not registered")
        return errors

    def catalog(self) -> list[dict]:
        """Return a human-readable catalog of all skills."""
        return [
            {
                "name": s.metadata.name,
                "description": s.metadata.description,
                "version": s.metadata.version,
                "permissions": str(s.metadata.permissions),
                "latency": s.metadata.latency.value,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "required": p.required,
                        "description": p.description,
                    }
                    for p in s.metadata.parameters
                ],
                "returns": s.metadata.returns,
                "dependencies": s.metadata.dependencies,
                "tags": s.metadata.tags,
                "cacheable": s.metadata.cacheable,
            }
            for s in self._skills.values()
        ]


# ═══════════════════════════════════════════════════════════════════════════
# AGENT RUNTIME
# ═══════════════════════════════════════════════════════════════════════════


class AgentRuntime:
    """
    The central orchestrator.

    Owns the skill registry, security policy, audit log, and shared resources
    (LLM provider, memory store). Executes skills in a sandboxed context
    with permission enforcement.
    """

    def __init__(
        self,
        provider: Any = None,  # ModelProvider
        memory: Any = None,  # MemoryStore
        state_path: str = "sentinel_state.json",
        policy: SecurityPolicy | None = None,
    ):
        self.provider = provider
        self.memory = memory
        self.state_path = state_path
        self.policy = policy or SecurityPolicy()
        self.registry = SkillRegistry()
        self.audit = AuditLog()
        self._result_cache: dict[str, SkillResult] = {}

    def register_skill(self, skill: Skill):
        self.registry.register(skill)

    def register_skills(self, *skills: Skill):
        for skill in skills:
            self.register_skill(skill)

    def execute_skill(
        self,
        skill_name: str,
        params: dict[str, Any],
        parent_invocation_id: str = "",
    ) -> SkillResult:
        """
        Execute a single skill with full permission checking and audit logging.
        """
        invocation_id = str(uuid.uuid4())
        start = time.monotonic()

        # 1. Resolve skill
        skill = self.registry.get(skill_name)
        if skill is None:
            result = SkillResult(
                skill_name=skill_name,
                success=False,
                data=None,
                error=f"Unknown skill: {skill_name}",
                invocation_id=invocation_id,
            )
            self._audit(
                result,
                skill_name,
                params,
                Permission.NONE,
                Permission.NONE,
                parent_invocation_id,
                start,
            )
            return result

        meta = skill.metadata

        # 2. Check policy: is this skill allowed?
        allowed, reason = self.policy.check_skill(skill_name)
        if not allowed:
            result = SkillResult(
                skill_name=skill_name,
                success=False,
                data=None,
                error=f"Policy denied: {reason}",
                invocation_id=invocation_id,
            )
            self._audit(
                result,
                skill_name,
                params,
                meta.permissions,
                Permission.NONE,
                parent_invocation_id,
                start,
            )
            return result

        # 3. Check budget
        budget_ok, budget_reason = self.policy.check_budget()
        if not budget_ok:
            result = SkillResult(
                skill_name=skill_name,
                success=False,
                data=None,
                error=f"Budget exceeded: {budget_reason}",
                invocation_id=invocation_id,
            )
            self._audit(
                result,
                skill_name,
                params,
                meta.permissions,
                Permission.NONE,
                parent_invocation_id,
                start,
            )
            return result

        # 4. Resolve permissions (requested ∩ allowed − denied)
        granted = self.policy.resolve_permissions(meta.permissions)

        # 5. Validate required parameters
        for p in meta.parameters:
            if p.required and p.name not in params:
                if p.default is not None:
                    params[p.name] = p.default
                else:
                    result = SkillResult(
                        skill_name=skill_name,
                        success=False,
                        data=None,
                        error=f"Missing required parameter: {p.name}",
                        invocation_id=invocation_id,
                    )
                    self._audit(
                        result,
                        skill_name,
                        params,
                        meta.permissions,
                        granted,
                        parent_invocation_id,
                        start,
                    )
                    return result

        # 6. Build sandboxed context
        context = SkillContext(
            params=params,
            llm=self.provider
            if (granted & (Permission.LLM_READ | Permission.LLM_WRITE))
            else None,
            memory=self.memory
            if (granted & (Permission.MEMORY_READ | Permission.MEMORY_WRITE))
            else None,
            state_path=self.state_path
            if (granted & (Permission.STATE_READ | Permission.STATE_WRITE))
            else None,
            permissions=granted,
            _runtime=self,
            invocation_id=invocation_id,
            parent_invocation_id=parent_invocation_id,
        )

        # 7. Check cache
        if meta.cacheable:
            cache_key = (
                f"{skill_name}:{json.dumps(params, sort_keys=True, default=str)}"
            )
            if cache_key in self._result_cache:
                cached = self._result_cache[cache_key]
                cached.metadata["cached"] = True
                return cached

        # 8. Execute
        try:
            result = skill.execute(context)
            result.invocation_id = invocation_id
            result.duration_ms = (time.monotonic() - start) * 1000

            # Record usage
            if result.token_usage > 0:
                self.policy.record_usage(llm_calls=1, tokens=result.token_usage)

            # Cache if applicable
            if meta.cacheable and result.success:
                self._result_cache[cache_key] = result

        except Exception as exc:
            result = SkillResult(
                skill_name=skill_name,
                success=False,
                data=None,
                error=f"{type(exc).__name__}: {exc}",
                invocation_id=invocation_id,
                duration_ms=(time.monotonic() - start) * 1000,
            )

        # 9. Audit
        self._audit(
            result,
            skill_name,
            params,
            meta.permissions,
            granted,
            parent_invocation_id,
            start,
        )
        return result

    def execute_plan(self, plan: ExecutionPlan) -> list[SkillResult]:
        """Execute a multi-step plan, threading results between steps."""
        logger.info("Executing plan: %s (%d steps)", plan.goal, len(plan.steps))
        results: list[SkillResult] = []
        result_map: dict[str, SkillResult] = {}

        for i, step in enumerate(plan.steps):
            # Inject prior results into params if referenced
            enriched_params = dict(step.params)
            for dep_id in step.depends_on:
                if dep_id in result_map:
                    enriched_params[f"_dep_{dep_id}"] = result_map[dep_id].data

            result = self.execute_skill(step.skill_name, enriched_params)
            results.append(result)
            result_map[result.invocation_id] = result

            if not result.success:
                logger.warning(
                    "Plan step %d/%d failed (%s): %s — continuing",
                    i + 1,
                    len(plan.steps),
                    step.skill_name,
                    result.error,
                )

        return results

    def _audit(
        self,
        result: SkillResult,
        skill_name: str,
        params: dict,
        requested: Permission,
        granted: Permission,
        parent_id: str,
        start: float,
    ):
        self.audit.record(
            AuditEntry(
                invocation_id=result.invocation_id,
                parent_invocation_id=parent_id,
                skill_name=skill_name,
                params={k: str(v)[:200] for k, v in params.items()},
                permissions_requested=str(requested),
                permissions_granted=str(granted),
                success=result.success,
                error=result.error,
                duration_ms=result.duration_ms,
                token_usage=result.token_usage,
                timestamp=datetime.utcnow().isoformat(),
            )
        )
