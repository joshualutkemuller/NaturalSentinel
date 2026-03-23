"""
Agent framework — skill-based execution with permissions, planning, and audit.

This replaces the naive "prompt → JSON" pattern with a deliberate agent
architecture where every capability is a registered Skill with:

  - Declared permissions (read/write to memory, filesystem, network, LLM)
  - Input/output schemas
  - Cost estimates (token budget, latency class)
  - Dependency declarations (which other skills it may invoke)

The AgentRuntime is the orchestrator that:

  1. Receives a high-level goal (e.g. "scan SEC for new filings")
  2. Plans: selects which skills to invoke and in what order
  3. Checks permissions against the active policy
  4. Executes skills, passing results between them
  5. Records every step in an audit log
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum, Flag, auto
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# PERMISSIONS
# ═══════════════════════════════════════════════════════════════════════════


class Permission(Flag):
    """Granular capabilities a skill may request."""

    NONE = 0
    LLM_READ = auto()  # Call an LLM for analysis (read-only inference)
    LLM_WRITE = auto()  # Call an LLM to generate content that gets stored
    MEMORY_READ = auto()  # Read from the persistent memory store
    MEMORY_WRITE = auto()  # Write to the persistent memory store
    STATE_READ = auto()  # Read dedup / checkpoint state
    STATE_WRITE = auto()  # Write dedup / checkpoint state
    FETCH_LOCAL = auto()  # Read from local sample/cached data
    FETCH_NETWORK = auto()  # Make outbound HTTP requests (real API fetching)
    FILE_READ = auto()  # Read from the filesystem
    FILE_WRITE = auto()  # Write to the filesystem
    HUMAN_INPUT = auto()  # Request input/confirmation from a human


# Convenience groups
READONLY = (
    Permission.LLM_READ
    | Permission.MEMORY_READ
    | Permission.STATE_READ
    | Permission.FETCH_LOCAL
    | Permission.FILE_READ
)
STANDARD = READONLY | Permission.LLM_WRITE | Permission.MEMORY_WRITE | Permission.STATE_WRITE
FULL = STANDARD | Permission.FETCH_NETWORK | Permission.FILE_WRITE | Permission.HUMAN_INPUT


class LatencyClass(Enum):
    """Expected execution speed."""

    INSTANT = "instant"  # < 100ms — pure computation
    FAST = "fast"  # < 2s — local DB / cached data
    MODERATE = "moderate"  # 2-15s — single LLM call
    SLOW = "slow"  # 15-60s — multiple LLM calls or network
    BATCH = "batch"  # > 60s — full scan cycle


# ═══════════════════════════════════════════════════════════════════════════
# SKILL DEFINITION
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
    dependencies: list[str] = field(default_factory=list)  # Other skill names this may call
    max_token_budget: int = 4096  # Soft cap on LLM tokens per invocation
    cacheable: bool = False  # Can results be cached for identical inputs?
    tags: list[str] = field(default_factory=list)


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

    skill_name: str
    success: bool
    data: Any  # The actual output
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
    depends_on: list[str] = field(default_factory=list)  # invocation IDs this step waits for
    description: str = ""


@dataclass
class ExecutionPlan:
    """Ordered sequence of skill invocations to achieve a goal."""

    goal: str
    steps: list[PlanStep]
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# ═══════════════════════════════════════════════════════════════════════════
# AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class AuditEntry:
    """Immutable record of a skill invocation."""

    invocation_id: str
    parent_invocation_id: str
    skill_name: str
    params: dict[str, Any]
    permissions_granted: str  # String repr of Permission flags
    permissions_requested: str
    success: bool
    error: str
    duration_ms: float
    token_usage: int
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


class AuditLog:
    """Append-only execution audit trail."""

    def __init__(self):
        self._entries: list[AuditEntry] = []

    def record(self, entry: AuditEntry):
        self._entries.append(entry)
        level = logging.INFO if entry.success else logging.WARNING
        logger.log(
            level,
            "[AUDIT] %s %s — %s (%.0fms, %d tokens)",
            entry.skill_name,
            entry.invocation_id[:8],
            "OK" if entry.success else f"FAIL: {entry.error}",
            entry.duration_ms,
            entry.token_usage,
        )

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    def for_skill(self, skill_name: str) -> list[AuditEntry]:
        return [e for e in self._entries if e.skill_name == skill_name]

    def failures(self) -> list[AuditEntry]:
        return [e for e in self._entries if not e.success]

    def summary(self) -> dict:
        total = len(self._entries)
        failures = len(self.failures())
        total_ms = sum(e.duration_ms for e in self._entries)
        total_tokens = sum(e.token_usage for e in self._entries)
        return {
            "total_invocations": total,
            "failures": failures,
            "success_rate": (total - failures) / total if total else 0,
            "total_duration_ms": round(total_ms, 1),
            "total_tokens": total_tokens,
            "skills_used": list({e.skill_name for e in self._entries}),
        }

    def export_json(self) -> str:
        return json.dumps([e.to_dict() for e in self._entries], indent=2)


# ═══════════════════════════════════════════════════════════════════════════
# SECURITY POLICY
# ═══════════════════════════════════════════════════════════════════════════


class SecurityPolicy:
    """
    Controls which permissions are actually granted at runtime.

    Even if a skill *requests* FETCH_NETWORK, the policy can deny it.
    This allows running in sandboxed/offline modes.
    """

    def __init__(
        self,
        allowed: Permission = STANDARD,
        denied: Permission = Permission.NONE,
        max_llm_calls_per_run: int = 50,
        max_total_tokens: int = 100_000,
        allowed_skills: set[str] | None = None,
        denied_skills: set[str] | None = None,
    ):
        self.allowed = allowed
        self.denied = denied
        self.max_llm_calls_per_run = max_llm_calls_per_run
        self.max_total_tokens = max_total_tokens
        self.allowed_skills = allowed_skills  # None = all allowed
        self.denied_skills = denied_skills or set()
        self._llm_calls = 0
        self._total_tokens = 0

    def check_skill(self, skill_name: str) -> tuple[bool, str]:
        """Check if a skill is allowed to run at all."""
        if skill_name in self.denied_skills:
            return False, f"Skill '{skill_name}' is explicitly denied by policy"
        if self.allowed_skills is not None and skill_name not in self.allowed_skills:
            return False, f"Skill '{skill_name}' is not in the allowed set"
        return True, ""

    def resolve_permissions(self, requested: Permission) -> Permission:
        """Return the intersection of requested, allowed, and not-denied."""
        return (requested & self.allowed) & ~self.denied

    def check_budget(self) -> tuple[bool, str]:
        """Check if we're still within token/call budget."""
        if self._llm_calls >= self.max_llm_calls_per_run:
            return (
                False,
                f"LLM call budget exhausted ({self._llm_calls}/{self.max_llm_calls_per_run})",
            )
        if self._total_tokens >= self.max_total_tokens:
            return False, f"Token budget exhausted ({self._total_tokens}/{self.max_total_tokens})"
        return True, ""

    def record_usage(self, llm_calls: int = 0, tokens: int = 0):
        self._llm_calls += llm_calls
        self._total_tokens += tokens

    def reset_counters(self):
        self._llm_calls = 0
        self._total_tokens = 0


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
        logger.debug("Registered skill: %s v%s [%s]", meta.name, meta.version, meta.permissions)

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_skills(self) -> list[SkillMetadata]:
        return [s.metadata for s in self._skills.values()]

    def find_by_tag(self, tag: str) -> list[SkillMetadata]:
        return [s.metadata for s in self._skills.values() if tag in s.metadata.tags]

    def find_by_permission(self, perm: Permission) -> list[SkillMetadata]:
        """Find all skills that require a specific permission."""
        return [s.metadata for s in self._skills.values() if s.metadata.permissions & perm]

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
            llm=self.provider if (granted & (Permission.LLM_READ | Permission.LLM_WRITE)) else None,
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
            cache_key = f"{skill_name}:{json.dumps(params, sort_keys=True, default=str)}"
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
            result, skill_name, params, meta.permissions, granted, parent_invocation_id, start
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
