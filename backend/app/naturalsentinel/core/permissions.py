"""Permission flags and policy for skill execution.

Defines what a Skill is allowed to do at runtime. The Permission flag enum
is declared by each Skill; the SecurityPolicy intersects declared
permissions with the runtime-wide allowed/denied sets.

This was previously part of ``app.naturalsentinel.agent_framework``.
"""

from __future__ import annotations

from enum import Flag, auto

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
STANDARD = (
    READONLY | Permission.LLM_WRITE | Permission.MEMORY_WRITE | Permission.STATE_WRITE
)
FULL = (
    STANDARD | Permission.FETCH_NETWORK | Permission.FILE_WRITE | Permission.HUMAN_INPUT
)


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
            return (
                False,
                f"Token budget exhausted ({self._total_tokens}/{self.max_total_tokens})",
            )
        return True, ""

    def record_usage(self, llm_calls: int = 0, tokens: int = 0):
        self._llm_calls += llm_calls
        self._total_tokens += tokens

    def reset_counters(self):
        self._llm_calls = 0
        self._total_tokens = 0
