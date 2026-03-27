"""Audit event schema and emission helpers.

Every significant system action produces an :class:`AuditEvent` that is
written to the ``audit_log`` table.  The log is append-only by convention
(no UPDATE or DELETE after INSERT); callers should never delete rows.

Event taxonomy
--------------
FILING_INGESTED         A new filing was fetched and stored in episodic memory.
ANALYSIS_COMPLETED      LLM analysis completed successfully.
ANALYSIS_FAILED         LLM call or parsing failed; fallback was used.
FEEDBACK_RECORDED       A human reviewer submitted a correction.
ESCALATION_TRIGGERED    An escalation policy condition was met.
ESCALATION_RESOLVED     A previously triggered escalation was cleared by a reviewer.
FALLBACK_ACTIVATED      The system fell back to cached/partial analysis.
EVAL_RUN_COMPLETED      A quantitative evaluation run finished.
DRIFT_DETECTED          Extraction drift exceeded the configured threshold.
POLICY_APPLIED          An escalation or fallback policy check was executed.
MODEL_CHANGED           The configured LLM provider or model version changed.

Usage::

    event = AuditEvent.create(
        AuditEventType.ANALYSIS_COMPLETED,
        filing_id="SEC-2026-001",
        actor="system",
        payload={"severity": "high", "confidence": 0.82},
        severity=AuditSeverity.INFO,
    )
    memory_store.emit_audit_event(event)
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime


class AuditEventType(enum.StrEnum):
    FILING_INGESTED = "FILING_INGESTED"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    FEEDBACK_RECORDED = "FEEDBACK_RECORDED"
    ESCALATION_TRIGGERED = "ESCALATION_TRIGGERED"
    ESCALATION_RESOLVED = "ESCALATION_RESOLVED"
    FALLBACK_ACTIVATED = "FALLBACK_ACTIVATED"
    EVAL_RUN_COMPLETED = "EVAL_RUN_COMPLETED"
    DRIFT_DETECTED = "DRIFT_DETECTED"
    POLICY_APPLIED = "POLICY_APPLIED"
    MODEL_CHANGED = "MODEL_CHANGED"


class AuditSeverity(enum.StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class AuditEvent:
    """A single immutable audit log record."""

    event_id: str
    event_type: str  # AuditEventType value
    actor: str  # "system" | user identifier
    timestamp: str  # ISO UTC
    severity: str  # AuditSeverity value
    filing_id: str | None = None
    trace_id: str | None = None
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def create(
        cls,
        event_type: AuditEventType,
        actor: str = "system",
        filing_id: str | None = None,
        trace_id: str | None = None,
        payload: dict | None = None,
        severity: AuditSeverity = AuditSeverity.INFO,
    ) -> AuditEvent:
        """Convenience factory — generates event_id and timestamp automatically."""
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=event_type.value,
            actor=actor,
            timestamp=datetime.utcnow().isoformat(),
            severity=severity.value,
            filing_id=filing_id,
            trace_id=trace_id,
            payload=payload or {},
        )


def severity_for_event(event_type: AuditEventType) -> AuditSeverity:
    """Return the default :class:`AuditSeverity` for a given event type."""
    critical = {AuditEventType.ESCALATION_TRIGGERED, AuditEventType.DRIFT_DETECTED}
    warnings = {
        AuditEventType.ANALYSIS_FAILED,
        AuditEventType.FALLBACK_ACTIVATED,
        AuditEventType.MODEL_CHANGED,
    }
    if event_type in critical:
        return AuditSeverity.HIGH
    if event_type in warnings:
        return AuditSeverity.WARNING
    return AuditSeverity.INFO
