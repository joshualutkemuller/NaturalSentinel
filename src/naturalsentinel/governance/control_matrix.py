"""Control Matrix — maps governance requirements to NaturalSentinel controls.

A control matrix (sometimes called a risk-and-control matrix or RACM) documents
which operational and regulatory requirements the system addresses, what specific
technical controls implement them, and where auditors can find evidence.

Usage::

    matrix = ControlMatrix.default()
    gaps = matrix.get_by_status("planned")
    print(matrix.coverage_summary())
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Control:
    """A single row in the control matrix."""

    control_id: str             # Unique identifier, e.g. "CTL-001"
    requirement: str            # The governance/regulatory requirement
    category: str               # "auditability" | "accuracy" | "explainability" |
                                #  "escalation" | "data_quality" | "model_risk"
    description: str            # What this control does
    implementation: str         # Where/how it is implemented in code
    evidence: str               # How an auditor can verify the control is active
    status: str = "implemented" # "implemented" | "partial" | "planned" | "not_applicable"
    owner: str = "Engineering"  # Team or role accountable for this control

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ControlMatrix:
    """Ordered collection of controls with summary helpers."""

    controls: list[Control] = field(default_factory=list)
    version: str = "1.0.0"
    last_reviewed: str = "2026-03-18"

    def get_by_status(self, status: str) -> list[Control]:
        """Return controls matching *status*."""
        return [c for c in self.controls if c.status == status]

    def get_by_category(self, category: str) -> list[Control]:
        """Return controls in a given *category*."""
        return [c for c in self.controls if c.category == category]

    def coverage_summary(self) -> dict:
        """Return counts by status and category."""
        by_status: dict[str, int] = {}
        by_cat: dict[str, int] = {}
        for c in self.controls:
            by_status[c.status] = by_status.get(c.status, 0) + 1
            by_cat[c.category] = by_cat.get(c.category, 0) + 1
        implemented = by_status.get("implemented", 0)
        total = len(self.controls)
        return {
            "total": total,
            "implemented": implemented,
            "partial": by_status.get("partial", 0),
            "planned": by_status.get("planned", 0),
            "not_applicable": by_status.get("not_applicable", 0),
            "coverage_pct": round(100 * implemented / total, 1) if total else 0.0,
            "by_category": by_cat,
            "by_status": by_status,
        }

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "last_reviewed": self.last_reviewed,
            "controls": [c.to_dict() for c in self.controls],
            "coverage_summary": self.coverage_summary(),
        }

    @classmethod
    def default(cls) -> "ControlMatrix":
        """Return the canonical NaturalSentinel control matrix."""
        return cls(controls=[
            # ── Auditability ─────────────────────────────────────────────
            Control(
                control_id="CTL-001",
                requirement="All system actions must be logged with sufficient detail "
                            "to reconstruct the sequence of events.",
                category="auditability",
                description="Immutable audit log captures every significant event "
                            "(filing ingestion, LLM analysis, feedback, escalation, "
                            "eval run) with event_type, filing_id, actor, payload, "
                            "severity, and timestamp.",
                implementation="audit_log SQLite table; write via MemoryStore.emit_audit_event()",
                evidence="SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 100;",
                status="implemented",
                owner="Engineering",
            ),
            Control(
                control_id="CTL-002",
                requirement="Human corrections and overrides must be recorded and "
                            "attributable.",
                category="auditability",
                description="feedback_log table records the filing_id, field, "
                            "old_value, new_value, reason, and created_at for every "
                            "analyst correction.",
                implementation="feedback_log table; MemoryStore.record_feedback()",
                evidence="SELECT * FROM feedback_log ORDER BY created_at DESC;",
                status="implemented",
                owner="Engineering",
            ),
            Control(
                control_id="CTL-003",
                requirement="System must retain a traceable record of each analysis "
                            "pipeline execution.",
                category="auditability",
                description="DecisionTrace records every pipeline step (prompt build, "
                            "LLM inference, parse, policy check, store) with timing, "
                            "token usage, and model provenance.",
                implementation="decision_traces table; lineage.trace.DecisionTrace",
                evidence="SELECT * FROM decision_traces WHERE filing_id = '<id>';",
                status="implemented",
                owner="Engineering",
            ),

            # ── Accuracy & Model Quality ──────────────────────────────────
            Control(
                control_id="CTL-004",
                requirement="Extraction accuracy must be measured quantitatively and "
                            "reported to stakeholders.",
                category="accuracy",
                description="RunEvaluationSkill computes per-field accuracy (exact "
                            "match, Jaccard, date match) over benchmark cases sourced "
                            "from feedback corrections, storing SuiteScore in eval_runs.",
                implementation="eval.scorer; skills.run_evaluation.RunEvaluationSkill",
                evidence="SELECT run_id, overall_accuracy, ece, run_at FROM eval_runs "
                         "ORDER BY run_at DESC LIMIT 5;",
                status="implemented",
                owner="Data Science",
            ),
            Control(
                control_id="CTL-005",
                requirement="Model confidence scores must be calibrated — stated "
                            "confidence should reflect actual accuracy.",
                category="accuracy",
                description="Calibration report (ECE, MCE, per-bucket accuracy) is "
                            "computed alongside each evaluation run and stored in "
                            "eval_runs.calibration_json.",
                implementation="eval.calibration.build_calibration_report()",
                evidence="SELECT ece, mce FROM eval_runs ORDER BY run_at DESC LIMIT 1;",
                status="implemented",
                owner="Data Science",
            ),
            Control(
                control_id="CTL-006",
                requirement="Extraction quality must be monitored for drift over time.",
                category="accuracy",
                description="DriftAnalyzer computes TV distance and effect size between "
                            "rolling time windows, flagging distribution shifts in "
                            "severity, confidence, business lines, and change type.",
                implementation="eval.drift.build_drift_report(); RunEvaluationSkill drift mode",
                evidence="Check drift_json in latest eval_run record.",
                status="implemented",
                owner="Data Science",
            ),

            # ── Explainability ────────────────────────────────────────────
            Control(
                control_id="CTL-007",
                requirement="Each extracted field must be attributable to a specific "
                            "passage in the source document.",
                category="explainability",
                description="FieldCitation records the verbatim source passage that "
                            "supports each extraction (severity, change_type, "
                            "compliance_deadline, etc.).",
                implementation="lineage.citation.FieldCitation; citations table; "
                               "ImpactAssessment.citations dict",
                evidence="SELECT citations FROM citations WHERE filing_id = '<id>';",
                status="implemented",
                owner="Engineering",
            ),
            Control(
                control_id="CTL-008",
                requirement="The model and provider used at each analysis step must be "
                            "recorded for reproducibility.",
                category="explainability",
                description="ModelProvenance captures provider, model_id, temperature, "
                            "max_tokens, and prompt template hash for each pipeline step.",
                implementation="lineage.provenance.ModelProvenance; stored in decision_traces",
                evidence="SELECT steps_json FROM decision_traces WHERE filing_id = '<id>';",
                status="implemented",
                owner="Engineering",
            ),
            Control(
                control_id="CTL-009",
                requirement="Prior/posterior belief tracking must be maintained so "
                            "analysts can see how confidence has evolved.",
                category="explainability",
                description="BeliefTrackerSkill maintains prior_confidence and "
                            "posterior_confidence per topic/domain, with delta drivers "
                            "and reversal risk scores stored in belief_states.",
                implementation="skills.belief_tracker.BeliefTrackerSkill; belief_states table",
                evidence="SELECT * FROM belief_states ORDER BY updated_at DESC;",
                status="implemented",
                owner="Engineering",
            ),

            # ── Escalation & Fallback ─────────────────────────────────────
            Control(
                control_id="CTL-010",
                requirement="Critical-severity filings and low-confidence assessments "
                            "must trigger human review.",
                category="escalation",
                description="EscalationPolicy evaluates each completed analysis against "
                            "configurable thresholds (severity, confidence, drift) and "
                            "emits an ESCALATION_TRIGGERED audit event.",
                implementation="governance.policy.EscalationPolicy; integrated into AnalyzeFilingSkill",
                evidence="SELECT * FROM audit_log WHERE event_type = 'ESCALATION_TRIGGERED';",
                status="implemented",
                owner="Risk Management",
            ),
            Control(
                control_id="CTL-011",
                requirement="System must degrade gracefully when the LLM provider is "
                            "unavailable.",
                category="escalation",
                description="FallbackPolicy specifies which cached analysis to use when "
                            "live inference fails, and records a FALLBACK_ACTIVATED "
                            "audit event.",
                implementation="governance.policy.FallbackPolicy; AnalyzeFilingSkill error path",
                evidence="SELECT * FROM audit_log WHERE event_type = 'FALLBACK_ACTIVATED';",
                status="implemented",
                owner="Engineering",
            ),

            # ── Data Quality ──────────────────────────────────────────────
            Control(
                control_id="CTL-012",
                requirement="Ingested filings must be de-duplicated.",
                category="data_quality",
                description="fetch_filings() de-duplicates by filing_id before "
                            "normalisation; episodic memory uses filing_id as PK.",
                implementation="fetchers.base._fetch_live(); memory store upsert logic",
                evidence="PRAGMA table_info(episodic_memory); SELECT COUNT(DISTINCT id) "
                         "FROM episodic_memory;",
                status="implemented",
                owner="Engineering",
            ),
            Control(
                control_id="CTL-013",
                requirement="Source documents must be attributed to their originating "
                            "regulatory body and URL.",
                category="data_quality",
                description="RegulatoryFiling carries domain (regulatory body) and "
                            "source_url; both are persisted to episodic_memory and "
                            "included in every analysis.",
                implementation="models.RegulatoryFiling; memory store episodic record",
                evidence="SELECT source_url, domain FROM episodic_memory LIMIT 10;",
                status="implemented",
                owner="Engineering",
            ),

            # ── Model Risk ────────────────────────────────────────────────
            Control(
                control_id="CTL-014",
                requirement="Failure modes must be classified and documented.",
                category="model_risk",
                description="FailureTaxonomy provides a coded taxonomy of failure "
                            "categories (LLM_UNAVAILABLE, LLM_HALLUCINATION, "
                            "INGESTION_FAILURE, etc.) with severity and remediation "
                            "guidance.",
                implementation="governance.failure_taxonomy.FAILURE_TAXONOMY",
                evidence="from naturalsentinel.governance.failure_taxonomy import "
                         "FAILURE_TAXONOMY; print(list(FAILURE_TAXONOMY.keys()))",
                status="implemented",
                owner="Data Science",
            ),
            Control(
                control_id="CTL-015",
                requirement="A model card documenting intended use, limitations, and "
                            "evaluation results must be maintained.",
                category="model_risk",
                description="ModelCard dataclass captures name, version, provider, "
                            "intended_use, out_of_scope_uses, known_limitations, "
                            "ethical_considerations, and evaluation metrics.",
                implementation="governance.model_card.ModelCard.default()",
                evidence="from naturalsentinel.governance import ModelCard; "
                         "print(ModelCard.default().to_dict())",
                status="implemented",
                owner="Risk Management",
            ),
        ])
