"""Escalation and fallback policies.

Policies codify the conditions under which NaturalSentinel should escalate
to human review (EscalationPolicy) and the degraded-mode behaviour when the
LLM or a data source is unavailable (FallbackPolicy).

Both policies are designed to be configurable via JSON so operations teams
can tune thresholds without code changes.

Usage::

    policy = EscalationPolicy.default()
    reasons = policy.evaluate(impact_dict, calibration_ece=0.12, drift_detected=True)
    if reasons:
        # emit ESCALATION_TRIGGERED audit event

    fallback = FallbackPolicy.default()
    action = fallback.select("LLM_UNAVAILABLE", {"cached_age_hours": 5})
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


# ---------------------------------------------------------------------------
# Escalation policy
# ---------------------------------------------------------------------------

@dataclass
class EscalationTrigger:
    """A single condition that can trigger escalation."""

    condition_id: str       # Stable ID, e.g. "critical_severity"
    description: str        # Human-readable explanation
    field: str              # Key in the analysis dict to inspect, or special key
    operator: str           # "eq" | "gte" | "lte" | "in" | "true"
    threshold: object       # Comparison value
    reason_template: str    # Message included in the escalation reason


@dataclass
class EscalationPolicy:
    """Policy that evaluates a completed analysis and returns triggered reasons."""

    name: str
    triggers: list[EscalationTrigger] = field(default_factory=list)
    block_alert_on_escalation: bool = True   # If True, hold automated alerts

    def evaluate(
        self,
        impact: dict,
        calibration_ece: Optional[float] = None,
        drift_detected: Optional[bool] = None,
    ) -> list[str]:
        """Evaluate all triggers against *impact* and return triggered reason strings.

        Args:
            impact: Parsed impact assessment dict (severity, confidence, etc.).
            calibration_ece: Latest ECE from the calibration report (optional).
            drift_detected: Whether drift was flagged in the latest eval run.

        Returns:
            List of human-readable escalation reason strings.  Empty = no escalation.
        """
        reasons: list[str] = []
        for t in self.triggers:
            triggered = False
            value = impact.get(t.field)

            if t.field == "_calibration_ece":
                value = calibration_ece
            elif t.field == "_drift_detected":
                value = drift_detected

            if value is None:
                continue

            if t.operator == "eq":
                triggered = str(value).lower() == str(t.threshold).lower()
            elif t.operator == "gte":
                try:
                    triggered = float(value) >= float(t.threshold)
                except (TypeError, ValueError):
                    pass
            elif t.operator == "lte":
                try:
                    triggered = float(value) <= float(t.threshold)
                except (TypeError, ValueError):
                    pass
            elif t.operator == "in":
                triggered = str(value).lower() in [str(x).lower() for x in t.threshold]
            elif t.operator == "true":
                triggered = bool(value)

            if triggered:
                reasons.append(
                    t.reason_template.format(value=value, threshold=t.threshold)
                )

        return reasons

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def default(cls) -> "EscalationPolicy":
        """Return the default NaturalSentinel escalation policy."""
        return cls(
            name="default",
            block_alert_on_escalation=True,
            triggers=[
                EscalationTrigger(
                    condition_id="critical_severity",
                    description="Any CRITICAL severity finding requires human review",
                    field="severity",
                    operator="eq",
                    threshold="critical",
                    reason_template="Severity is CRITICAL — mandatory human review before alerting",
                ),
                EscalationTrigger(
                    condition_id="low_confidence",
                    description="Confidence below 0.40 indicates high uncertainty",
                    field="confidence",
                    operator="lte",
                    threshold=0.40,
                    reason_template="Confidence {value:.2f} is below threshold {threshold} — assessment unreliable",
                ),
                EscalationTrigger(
                    condition_id="calibration_warning",
                    description="ECE above 0.15 means confidence scores are poorly calibrated",
                    field="_calibration_ece",
                    operator="gte",
                    threshold=0.15,
                    reason_template="Calibration ECE {value:.3f} exceeds warning threshold {threshold} — confidence may be misleading",
                ),
                EscalationTrigger(
                    condition_id="drift_detected",
                    description="Extraction drift indicates possible model or corpus change",
                    field="_drift_detected",
                    operator="true",
                    threshold=True,
                    reason_template="Extraction drift detected — verify outputs before distributing alerts",
                ),
            ],
        )

    @classmethod
    def from_dict(cls, data: dict) -> "EscalationPolicy":
        triggers = [EscalationTrigger(**t) for t in data.get("triggers", [])]
        return cls(
            name=data.get("name", "custom"),
            triggers=triggers,
            block_alert_on_escalation=data.get("block_alert_on_escalation", True),
        )


# ---------------------------------------------------------------------------
# Fallback policy
# ---------------------------------------------------------------------------

FALLBACK_ACTIONS: dict[str, str] = {
    "use_cached":        "Use the cached analysis from the last successful run",
    "use_partial":       "Use the abstract/title only — full-text analysis skipped",
    "require_human":     "Flag for mandatory human review; do not emit automated alert",
    "use_stub":          "Return a minimal stub assessment with confidence=0.0",
    "retry_later":       "Queue the filing for retry at next scan cycle",
}


@dataclass
class FallbackPolicy:
    """Policy that selects a degraded-mode action for a given failure reason."""

    name: str
    cache_max_age_hours: int = 24       # Use cached analysis if this fresh
    min_confidence_for_alert: float = 0.40  # Don't auto-alert below this
    rules: dict[str, str] = field(default_factory=dict)  # failure_code → action_key

    def select(self, failure_code: str, context: Optional[dict] = None) -> dict:
        """Select the fallback action for *failure_code*.

        Returns a dict with keys:
            action   — action_key (e.g. "use_cached")
            label    — human-readable description
            context  — the passed-in context dict
        """
        context = context or {}
        action_key = self.rules.get(failure_code, "require_human")

        # Special case: if cached analysis is recent enough, prefer it
        if action_key == "use_cached":
            cache_age = context.get("cached_age_hours")
            if cache_age is not None and cache_age > self.cache_max_age_hours:
                action_key = "require_human"

        label = FALLBACK_ACTIONS.get(action_key, action_key)
        return {
            "failure_code": failure_code,
            "action": action_key,
            "label": label,
            "context": context,
        }

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def default(cls) -> "FallbackPolicy":
        """Return the default NaturalSentinel fallback policy."""
        return cls(
            name="default",
            cache_max_age_hours=24,
            min_confidence_for_alert=0.40,
            rules={
                "LLM_UNAVAILABLE":      "use_cached",
                "LLM_REFUSED":          "require_human",
                "LLM_MALFORMED_OUTPUT": "use_partial",
                "INGESTION_FAILURE":    "retry_later",
                "PARSING_ERROR":        "use_partial",
                "CALIBRATION_DRIFT":    "require_human",
                "EXTRACTION_DRIFT":     "require_human",
                "SCHEMA_VIOLATION":     "use_stub",
                "ESCALATION_REQUIRED":  "require_human",
                "MEMORY_ERROR":         "use_stub",
            },
        )

    @classmethod
    def from_dict(cls, data: dict) -> "FallbackPolicy":
        return cls(
            name=data.get("name", "custom"),
            cache_max_age_hours=data.get("cache_max_age_hours", 24),
            min_confidence_for_alert=data.get("min_confidence_for_alert", 0.40),
            rules=data.get("rules", {}),
        )
