"""add naturalsentinel tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-26 00:00:01.000000

Creates all 9 NaturalSentinel domain tables:
  ns_memories, ns_entity_relations, ns_feedback_log,
  ns_belief_states, ns_belief_history, ns_eval_runs,
  ns_audit_log, ns_decision_traces, ns_citations
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None

NS_TABLES = [
    "ns_memories",
    "ns_entity_relations",
    "ns_feedback_log",
    "ns_belief_states",
    "ns_belief_history",
    "ns_eval_runs",
    "ns_audit_log",
    "ns_decision_traces",
    "ns_citations",
]


def upgrade() -> None:
    # ns_memories — episodic, entity, precedent records
    op.create_table(
        "ns_memories",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("memory_type", sa.String(), nullable=False),
        sa.Column("namespace", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("embedding_text", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.create_index("ix_ns_memories_type", "ns_memories", ["memory_type"])
    op.create_index("ix_ns_memories_ns", "ns_memories", ["namespace"])
    op.create_index("ix_ns_memories_key", "ns_memories", ["key"])

    # ns_entity_relations — knowledge graph edges
    op.create_table(
        "ns_entity_relations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("relation", sa.String(), nullable=False),
        sa.Column("target", sa.String(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("source", "relation", "target", name="uq_ns_er_edge"),
    )
    op.create_index("ix_ns_er_source", "ns_entity_relations", ["source"])
    op.create_index("ix_ns_er_target", "ns_entity_relations", ["target"])

    # ns_feedback_log — human corrections
    op.create_table(
        "ns_feedback_log",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("filing_id", sa.String(), nullable=False),
        sa.Column("field", sa.String(), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_ns_fl_filing_id", "ns_feedback_log", ["filing_id"])

    # ns_belief_states — prior/posterior confidence per (topic, domain)
    op.create_table(
        "ns_belief_states",
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("prior_confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("posterior_confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("delta_confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("delta_drivers", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("stability_score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("reversal_risk", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("observation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_filing_id", sa.String(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("topic", "domain"),
    )
    op.create_index("ix_ns_bs_domain", "ns_belief_states", ["domain"])

    # ns_belief_history — full confidence observation history
    op.create_table(
        "ns_belief_history",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("delta_confidence", sa.Float(), nullable=False),
        sa.Column("delta_drivers", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("filing_id", sa.String(), nullable=False, server_default=""),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_ns_bh_topic_domain", "ns_belief_history", ["topic", "domain"])

    # ns_eval_runs — quantitative evaluation results
    op.create_table(
        "ns_eval_runs",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("provider_tag", sa.String(), nullable=False, server_default="default"),
        sa.Column("suite_name", sa.String(), nullable=False, server_default="feedback_log"),
        sa.Column("n_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overall_accuracy", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("per_field_accuracy", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("domain_breakdown", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("n_fields_evaluated", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("ece", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("mce", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("calibration_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("drift_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "run_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_ns_er_provider_tag", "ns_eval_runs", ["provider_tag"])
    op.create_index("ix_ns_er_run_at", "ns_eval_runs", ["run_at"])

    # ns_audit_log — immutable governance events
    op.create_table(
        "ns_audit_log",
        sa.Column("event_id", sa.String(), primary_key=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("filing_id", sa.String(), nullable=True),
        sa.Column("actor", sa.String(), nullable=False, server_default="system"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("severity", sa.String(), nullable=False, server_default="INFO"),
        sa.Column("trace_id", sa.String(), nullable=True),
    )
    op.create_index("ix_ns_al_event_type", "ns_audit_log", ["event_type"])
    op.create_index("ix_ns_al_filing_id", "ns_audit_log", ["filing_id"])
    op.create_index("ix_ns_al_timestamp", "ns_audit_log", ["timestamp"])
    op.create_index("ix_ns_al_severity", "ns_audit_log", ["severity"])

    # ns_decision_traces — lineage per filing analysis
    op.create_table(
        "ns_decision_traces",
        sa.Column("trace_id", sa.String(), primary_key=True),
        sa.Column("filing_id", sa.String(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_duration_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overall_status", sa.String(), nullable=False, server_default="ok"),
        sa.Column("steps_json", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.create_index("ix_ns_dt_filing_id", "ns_decision_traces", ["filing_id"])
    op.create_index("ix_ns_dt_started_at", "ns_decision_traces", ["started_at"])

    # ns_citations — source citations per filing
    op.create_table(
        "ns_citations",
        sa.Column("filing_id", sa.String(), primary_key=True),
        sa.Column("source_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("citations_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "extracted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )


def downgrade() -> None:
    for table in reversed(NS_TABLES):
        op.drop_table(table)
