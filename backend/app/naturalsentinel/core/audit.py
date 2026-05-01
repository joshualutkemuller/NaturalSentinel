"""Audit log for skill invocations.

Every skill execution writes an AuditEntry to an append-only AuditLog
on the AgentRuntime. The log captures permissions requested vs granted,
success/failure, duration, token usage, and parent/child invocation IDs
so cross-skill orchestration can be traced.

This was previously part of ``app.naturalsentinel.agent_framework``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any

logger = logging.getLogger(__name__)


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
