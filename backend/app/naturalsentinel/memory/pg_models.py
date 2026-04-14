"""SQLModel table definitions for PostgreSQL-backed NaturalSentinel memory.

These mirror the 9 tables defined in schema.py (SQLite) but use:
- UUID primary keys instead of AUTOINCREMENT integers
- sa.JSON for JSON columns instead of TEXT
- sa.DateTime(timezone=True) for timestamps
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


class PgMemory(SQLModel, table=True):
    """Episodic, entity, and precedent memory records."""

    __tablename__ = "ns_memories"

    id: str = Field(primary_key=True, default_factory=_uuid)
    memory_type: str = Field(nullable=False, index=True)
    namespace: str = Field(nullable=False, index=True)
    key: str = Field(nullable=False, index=True)
    content: Any = Field(default={}, sa_column=sa.Column(sa.JSON, nullable=False))
    embedding_text: str = Field(default="", nullable=False)
    created_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    access_count: int = Field(default=0, nullable=False)
    relevance_score: float = Field(default=1.0, nullable=False)


class PgEntityRelation(SQLModel, table=True):
    """Knowledge graph edges between entities."""

    __tablename__ = "ns_entity_relations"
    __table_args__ = (sa.UniqueConstraint("source", "relation", "target"),)

    id: str = Field(primary_key=True, default_factory=_uuid)
    source: str = Field(nullable=False, index=True)
    relation: str = Field(nullable=False)
    target: str = Field(nullable=False, index=True)
    weight: float = Field(default=1.0, nullable=False)
    context: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )


class PgFeedbackLog(SQLModel, table=True):
    """Human corrections recorded against stored filings."""

    __tablename__ = "ns_feedback_log"

    id: str = Field(primary_key=True, default_factory=_uuid)
    filing_id: str = Field(nullable=False, index=True)
    field: str = Field(nullable=False)
    old_value: str | None = Field(default=None, nullable=True)
    new_value: str | None = Field(default=None, nullable=True)
    reason: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )


class PgBeliefState(SQLModel, table=True):
    """Prior/posterior confidence tracking per (topic, domain) pair."""

    __tablename__ = "ns_belief_states"
    __table_args__ = (sa.PrimaryKeyConstraint("topic", "domain"),)

    topic: str = Field(nullable=False)
    domain: str = Field(nullable=False, index=True)
    prior_confidence: float = Field(default=0.5, nullable=False)
    posterior_confidence: float = Field(default=0.5, nullable=False)
    delta_confidence: float = Field(default=0.0, nullable=False)
    delta_drivers: Any = Field(default=[], sa_column=sa.Column(sa.JSON, nullable=False))
    stability_score: float = Field(default=1.0, nullable=False)
    reversal_risk: float = Field(default=0.1, nullable=False)
    observation_count: int = Field(default=0, nullable=False)
    last_filing_id: str = Field(default="", nullable=False)
    created_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )


class PgBeliefHistory(SQLModel, table=True):
    """Full history of every confidence observation for a (topic, domain) pair."""

    __tablename__ = "ns_belief_history"

    id: str = Field(primary_key=True, default_factory=_uuid)
    topic: str = Field(nullable=False, index=True)
    domain: str = Field(nullable=False, index=True)
    confidence: float = Field(nullable=False)
    delta_confidence: float = Field(nullable=False)
    delta_drivers: Any = Field(default=[], sa_column=sa.Column(sa.JSON, nullable=False))
    filing_id: str = Field(default="", nullable=False)
    observed_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )


class PgEvalRun(SQLModel, table=True):
    """Quantitative evaluation run results."""

    __tablename__ = "ns_eval_runs"

    run_id: str = Field(primary_key=True, default_factory=_uuid)
    provider_tag: str = Field(default="default", nullable=False, index=True)
    suite_name: str = Field(default="feedback_log", nullable=False)
    n_cases: int = Field(default=0, nullable=False)
    overall_accuracy: float = Field(default=0.0, nullable=False)
    per_field_accuracy: Any = Field(
        default={}, sa_column=sa.Column(sa.JSON, nullable=False)
    )
    domain_breakdown: Any = Field(
        default={}, sa_column=sa.Column(sa.JSON, nullable=False)
    )
    n_fields_evaluated: Any = Field(
        default={}, sa_column=sa.Column(sa.JSON, nullable=False)
    )
    ece: float = Field(default=0.0, nullable=False)
    mce: float = Field(default=0.0, nullable=False)
    calibration_json: Any = Field(
        default={}, sa_column=sa.Column(sa.JSON, nullable=False)
    )
    drift_json: Any = Field(default={}, sa_column=sa.Column(sa.JSON, nullable=False))
    run_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, index=True),
    )


class PgAuditEvent(SQLModel, table=True):
    """Immutable governance audit log (append-only by application convention)."""

    __tablename__ = "ns_audit_log"

    event_id: str = Field(primary_key=True, default_factory=_uuid)
    event_type: str = Field(nullable=False, index=True)
    filing_id: str | None = Field(default=None, nullable=True, index=True)
    actor: str = Field(default="system", nullable=False)
    payload: Any = Field(default={}, sa_column=sa.Column(sa.JSON, nullable=False))
    timestamp: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, index=True),
    )
    severity: str = Field(default="INFO", nullable=False, index=True)
    trace_id: str | None = Field(default=None, nullable=True)


class PgDecisionTrace(SQLModel, table=True):
    """Decision traces for filing analyses (lineage)."""

    __tablename__ = "ns_decision_traces"

    trace_id: str = Field(primary_key=True, default_factory=_uuid)
    filing_id: str = Field(nullable=False, index=True)
    started_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, index=True),
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    total_duration_ms: float = Field(default=0.0, nullable=False)
    total_tokens: int = Field(default=0, nullable=False)
    overall_status: str = Field(default="ok", nullable=False)
    steps_json: Any = Field(default=[], sa_column=sa.Column(sa.JSON, nullable=False))


class PgCitation(SQLModel, table=True):
    """Field citations extracted per filing (lineage)."""

    __tablename__ = "ns_citations"

    filing_id: str = Field(primary_key=True)
    source_url: str = Field(default="", nullable=False)
    citations_json: Any = Field(
        default=[], sa_column=sa.Column(sa.JSON, nullable=False)
    )
    extracted_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )


class PgDocument(SQLModel, table=True):
    """Tracks user-uploaded documents (contracts, policies, medical records).

    Complements the OpenViking filesystem representation. Not used for
    programmatically-fetched regulatory filings — those are tracked via
    ns_memories + ns_state_filings Qdrant collection.
    """

    __tablename__ = "ns_documents"

    doc_id: str = Field(primary_key=True, default_factory=_uuid)
    title: str = Field(default="", nullable=False)
    doc_type: str = Field(default="generic", nullable=False, index=True)
    file_name: str = Field(default="", nullable=False)
    file_size: int = Field(default=0, nullable=False)
    viking_uri: str = Field(default="", nullable=False, index=True)
    section_count: int = Field(default=0, nullable=False)
    status: str = Field(default="processing", nullable=False, index=True)
    metadata_json: Any = Field(default={}, sa_column=sa.Column(sa.JSON, nullable=False))
    structure_json: Any = Field(
        default={}, sa_column=sa.Column(sa.JSON, nullable=False)
    )
    created_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, index=True),
    )
    updated_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    created_by: str = Field(default="", nullable=False, index=True)


class PgProcessDefinition(SQLModel, table=True):
    """Registered document review process definitions."""

    __tablename__ = "ns_process_definitions"

    name: str = Field(primary_key=True)
    version: str = Field(default="1.0", nullable=False)
    description: str = Field(default="", nullable=False)
    doc_types: Any = Field(default=[], sa_column=sa.Column(sa.JSON, nullable=False))
    step_count: int = Field(default=0, nullable=False)
    definition_md: str = Field(default="", nullable=False)
    viking_uri: str = Field(default="", nullable=False)
    created_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    created_by: str = Field(default="", nullable=False)


class PgProcessExecution(SQLModel, table=True):
    """State tracker for an in-progress document review process execution."""

    __tablename__ = "ns_process_executions"

    execution_id: str = Field(primary_key=True, default_factory=_uuid)
    session_id: str = Field(default="", nullable=False, index=True)
    process_name: str = Field(default="", nullable=False, index=True)
    doc_ids: Any = Field(default=[], sa_column=sa.Column(sa.JSON, nullable=False))
    current_step: int = Field(default=0, nullable=False)
    total_steps: int = Field(default=0, nullable=False)
    completed_steps: int = Field(default=0, nullable=False)
    flagged_steps: int = Field(default=0, nullable=False)
    status: str = Field(default="in_progress", nullable=False, index=True)
    started_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    findings_json: Any = Field(default={}, sa_column=sa.Column(sa.JSON, nullable=False))
