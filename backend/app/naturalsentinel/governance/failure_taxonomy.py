"""Failure taxonomy — coded classification of NaturalSentinel failure modes.

Every operational failure should be classified against this taxonomy so that
root-cause analysis, escalation routing, and remediation guidance are
consistent across the system.

Usage::

    from app.naturalsentinel.governance.failure_taxonomy import FAILURE_TAXONOMY, FailureRecord

    category = FAILURE_TAXONOMY["LLM_UNAVAILABLE"]
    print(category.remediation)

    rec = FailureRecord.create(
        "LLM_UNAVAILABLE",
        filing_id="SEC-001",
        context={"provider": "anthropic", "status_code": 529},
    )
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass
class FailureCategory:
    """Static descriptor for a class of failure."""

    code: str
    name: str
    description: str
    severity: str  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    remediation: str  # Suggested corrective action
    auto_escalate: bool  # Whether this class of failure triggers auto-escalation
    impacts: list[str] = field(default_factory=list)  # Downstream systems affected

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FailureRecord:
    """An instance of a failure observed at runtime."""

    failure_id: str
    failure_code: str
    timestamp: str
    filing_id: str | None = None
    context: dict = field(default_factory=dict)
    resolved: bool = False
    resolution_notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def create(
        cls,
        failure_code: str,
        filing_id: str | None = None,
        context: dict | None = None,
    ) -> FailureRecord:
        """Factory that generates failure_id and timestamp."""
        return cls(
            failure_id=str(uuid.uuid4()),
            failure_code=failure_code,
            timestamp=datetime.utcnow().isoformat(),
            filing_id=filing_id,
            context=context or {},
        )


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

FAILURE_TAXONOMY: dict[str, FailureCategory] = {
    "LLM_UNAVAILABLE": FailureCategory(
        code="LLM_UNAVAILABLE",
        name="LLM Provider Unavailable",
        description=(
            "The configured LLM provider API is unreachable, returned a non-200 "
            "HTTP status, or timed out before returning a response."
        ),
        severity="HIGH",
        remediation=(
            "1. Verify provider API status (status.anthropic.com etc.). "
            "2. Check network egress and proxy configuration. "
            "3. Activate FallbackPolicy to use cached analysis if < 24 h old. "
            "4. Queue the filing for retry once the provider recovers."
        ),
        auto_escalate=True,
        impacts=["analysis", "alert"],
    ),
    "LLM_REFUSED": FailureCategory(
        code="LLM_REFUSED",
        name="LLM Content Refusal",
        description=(
            "The LLM returned a refusal or safety block rather than a structured "
            "impact assessment.  Typically occurs when filing text triggers safety "
            "filters."
        ),
        severity="MEDIUM",
        remediation=(
            "1. Review the filing text for content that may trigger safety filters. "
            "2. Consider rephrasing the prompt to focus on regulatory implications. "
            "3. Route to a human analyst if the content is legitimately sensitive. "
            "4. Log the refused filing_id for pattern analysis."
        ),
        auto_escalate=False,
        impacts=["analysis"],
    ),
    "LLM_MALFORMED_OUTPUT": FailureCategory(
        code="LLM_MALFORMED_OUTPUT",
        name="LLM Malformed JSON Output",
        description=(
            "The LLM returned text that could not be parsed as valid JSON, or the "
            "parsed JSON was missing required fields (severity, affected_business_lines, "
            "confidence)."
        ),
        severity="MEDIUM",
        remediation=(
            "1. Check parse_llm_json() logs for the raw response. "
            "2. The fallback assessment is used automatically; review it for accuracy. "
            "3. If recurring, review the system prompt for clarity. "
            "4. Consider increasing max_tokens if responses appear truncated."
        ),
        auto_escalate=False,
        impacts=["analysis", "calibration"],
    ),
    "INGESTION_FAILURE": FailureCategory(
        code="INGESTION_FAILURE",
        name="Filing Ingestion Failure",
        description=(
            "A live regulatory source (Federal Register, EDGAR, BIS, FINRA) returned "
            "an error or was unreachable during the ingestion phase."
        ),
        severity="MEDIUM",
        remediation=(
            "1. Check the specific source's status page. "
            "2. Verify network connectivity and rate-limit compliance. "
            "3. Fall back to sample data for the current scan cycle. "
            "4. Retry after the next scheduled source check."
        ),
        auto_escalate=False,
        impacts=["ingestion"],
    ),
    "PARSING_ERROR": FailureCategory(
        code="PARSING_ERROR",
        name="Document Parsing Error",
        description=(
            "The HTML or text extractor encountered an error processing the "
            "source document, resulting in empty or truncated raw_text."
        ),
        severity="LOW",
        remediation=(
            "1. Check the source_url for the affected filing. "
            "2. Attempt manual text extraction. "
            "3. If the document is PDF-only, note that PDF parsing is not "
            "fully supported; link text is used as fallback."
        ),
        auto_escalate=False,
        impacts=["ingestion", "analysis"],
    ),
    "CALIBRATION_DRIFT": FailureCategory(
        code="CALIBRATION_DRIFT",
        name="Confidence Calibration Drift",
        description=(
            "The most recent evaluation run reported an Expected Calibration Error "
            "(ECE) above the configured warning threshold (default 0.10), indicating "
            "that stated confidence scores no longer reliably predict accuracy."
        ),
        severity="HIGH",
        remediation=(
            "1. Review the calibration report in the latest eval_run record. "
            "2. Examine which confidence buckets are most miscalibrated. "
            "3. Consider adjusting the system prompt to request more conservative "
            "confidence values. "
            "4. Increase feedback collection volume to improve benchmark coverage."
        ),
        auto_escalate=True,
        impacts=["calibration", "alerting"],
    ),
    "EXTRACTION_DRIFT": FailureCategory(
        code="EXTRACTION_DRIFT",
        name="Extraction Pattern Drift",
        description=(
            "Statistical comparison of extraction outputs across consecutive time "
            "windows detected a significant shift (TV distance > threshold) in the "
            "distribution of severity, confidence, business lines, or change type."
        ),
        severity="HIGH",
        remediation=(
            "1. Review the drift_json in the latest eval_run. "
            "2. Check whether recent filings represent a genuine regulatory shift "
            "or a change in the source corpus. "
            "3. If model-induced, compare outputs before and after any recent model "
            "or prompt changes. "
            "4. Pause automated alerting until root cause is confirmed."
        ),
        auto_escalate=True,
        impacts=["alerting", "calibration"],
    ),
    "SCHEMA_VIOLATION": FailureCategory(
        code="SCHEMA_VIOLATION",
        name="Extraction Schema Violation",
        description=(
            "The parsed LLM output contained a field value that does not conform to "
            "the expected schema — e.g. an unrecognised severity level, an invalid "
            "date format, or a missing required field."
        ),
        severity="LOW",
        remediation=(
            "1. The affected field is set to its fallback default. "
            "2. Review the raw LLM response in the trace log. "
            "3. If systematic, update the system prompt to reinforce output "
            "constraints."
        ),
        auto_escalate=False,
        impacts=["analysis"],
    ),
    "ESCALATION_REQUIRED": FailureCategory(
        code="ESCALATION_REQUIRED",
        name="Human Escalation Required",
        description=(
            "An escalation policy condition was triggered — e.g. critical severity, "
            "low confidence, or detected drift — requiring human review before "
            "automated alerting proceeds."
        ),
        severity="HIGH",
        remediation=(
            "1. Route the filing to the designated compliance reviewer. "
            "2. Record the reviewer's decision in the feedback_log. "
            "3. After human review, mark the escalation as ESCALATION_RESOLVED "
            "in the audit_log."
        ),
        auto_escalate=False,  # Already the result of escalation
        impacts=["alerting", "compliance"],
    ),
    "MEMORY_ERROR": FailureCategory(
        code="MEMORY_ERROR",
        name="Memory / Database Error",
        description=(
            "A read or write operation on the SQLite memory store failed — e.g. "
            "due to a locked database, disk space exhaustion, or schema mismatch."
        ),
        severity="CRITICAL",
        remediation=(
            "1. Check disk space on the host running NaturalSentinel. "
            "2. Verify no other process holds an exclusive lock on the database. "
            "3. Run PRAGMA integrity_check; on the SQLite file. "
            "4. Restore from backup if data corruption is detected."
        ),
        auto_escalate=True,
        impacts=["analysis", "audit", "alerting"],
    ),
}


def classify(code: str) -> FailureCategory | None:
    """Look up a failure category by code.  Returns None for unknown codes."""
    return FAILURE_TAXONOMY.get(code)


def auto_escalate_codes() -> list[str]:
    """Return list of failure codes that trigger automatic escalation."""
    return [code for code, cat in FAILURE_TAXONOMY.items() if cat.auto_escalate]
