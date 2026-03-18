"""Governance artifacts for the NaturalSentinel regulatory monitoring system.

Modules
-------
model_card        ModelCard — AI system factsheet (intended use, limitations,
                  evaluation results, ethical considerations).
control_matrix    ControlMatrix / Control — mapping of governance requirements
                  to implemented technical controls with evidence pointers.
audit             AuditEvent / AuditEventType — immutable audit log schema
                  and event emission helpers.
failure_taxonomy  FAILURE_TAXONOMY — coded classification of operational failure
                  modes with severity ratings and remediation guidance.
policy            EscalationPolicy / FallbackPolicy — configurable rules for
                  human-review escalation and graceful degradation.
"""

from naturalsentinel.governance.model_card import ModelCard
from naturalsentinel.governance.control_matrix import Control, ControlMatrix
from naturalsentinel.governance.audit import (
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    severity_for_event,
)
from naturalsentinel.governance.failure_taxonomy import (
    FailureCategory,
    FailureRecord,
    FAILURE_TAXONOMY,
    classify as classify_failure,
    auto_escalate_codes,
)
from naturalsentinel.governance.policy import (
    EscalationTrigger,
    EscalationPolicy,
    FallbackPolicy,
    FALLBACK_ACTIONS,
)

__all__ = [
    # Model card
    "ModelCard",
    # Control matrix
    "Control",
    "ControlMatrix",
    # Audit
    "AuditEvent",
    "AuditEventType",
    "AuditSeverity",
    "severity_for_event",
    # Failure taxonomy
    "FailureCategory",
    "FailureRecord",
    "FAILURE_TAXONOMY",
    "classify_failure",
    "auto_escalate_codes",
    # Policy
    "EscalationTrigger",
    "EscalationPolicy",
    "FallbackPolicy",
    "FALLBACK_ACTIONS",
]
