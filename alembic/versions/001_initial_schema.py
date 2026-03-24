"""Initial schema — port from SQLite with pgvector support.

Revision ID: 001
Revises: None
Create Date: 2026-03-23
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # -- memories --
    op.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id              TEXT PRIMARY KEY,
            memory_type     TEXT NOT NULL,
            namespace       TEXT NOT NULL,
            key             TEXT NOT NULL,
            content         TEXT NOT NULL,
            embedding_text  TEXT NOT NULL,
            embedding       vector(1536),
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            access_count    INTEGER DEFAULT 0,
            relevance_score REAL DEFAULT 1.0
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_memories_ns   ON memories(namespace)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_memories_key  ON memories(key)")

    # -- entity_relations --
    op.execute("""
        CREATE TABLE IF NOT EXISTS entity_relations (
            id         SERIAL PRIMARY KEY,
            source     TEXT NOT NULL,
            relation   TEXT NOT NULL,
            target     TEXT NOT NULL,
            weight     REAL DEFAULT 1.0,
            context    TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(source, relation, target)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_er_source ON entity_relations(source)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_er_target ON entity_relations(target)")

    # -- feedback_log --
    op.execute("""
        CREATE TABLE IF NOT EXISTS feedback_log (
            id         SERIAL PRIMARY KEY,
            filing_id  TEXT NOT NULL,
            field      TEXT NOT NULL,
            old_value  TEXT,
            new_value  TEXT,
            reason     TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # -- belief_states --
    op.execute("""
        CREATE TABLE IF NOT EXISTS belief_states (
            topic                TEXT NOT NULL,
            domain               TEXT NOT NULL,
            prior_confidence     REAL NOT NULL DEFAULT 0.5,
            posterior_confidence REAL NOT NULL DEFAULT 0.5,
            delta_confidence     REAL NOT NULL DEFAULT 0.0,
            delta_drivers        TEXT NOT NULL DEFAULT '[]',
            stability_score      REAL NOT NULL DEFAULT 1.0,
            reversal_risk        REAL NOT NULL DEFAULT 0.1,
            observation_count    INTEGER NOT NULL DEFAULT 0,
            last_filing_id       TEXT NOT NULL DEFAULT '',
            created_at           TEXT NOT NULL,
            updated_at           TEXT NOT NULL,
            PRIMARY KEY (topic, domain)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_bs_domain ON belief_states(domain)")

    # -- belief_history --
    op.execute("""
        CREATE TABLE IF NOT EXISTS belief_history (
            id               SERIAL PRIMARY KEY,
            topic            TEXT NOT NULL,
            domain           TEXT NOT NULL,
            confidence       REAL NOT NULL,
            delta_confidence REAL NOT NULL,
            delta_drivers    TEXT NOT NULL DEFAULT '[]',
            filing_id        TEXT NOT NULL DEFAULT '',
            observed_at      TEXT NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_bh_topic_domain ON belief_history(topic, domain)")

    # -- eval_runs --
    op.execute("""
        CREATE TABLE IF NOT EXISTS eval_runs (
            run_id             TEXT PRIMARY KEY,
            provider_tag       TEXT NOT NULL DEFAULT 'default',
            suite_name         TEXT NOT NULL DEFAULT 'feedback_log',
            n_cases            INTEGER NOT NULL DEFAULT 0,
            overall_accuracy   REAL NOT NULL DEFAULT 0.0,
            per_field_accuracy TEXT NOT NULL DEFAULT '{}',
            domain_breakdown   TEXT NOT NULL DEFAULT '{}',
            n_fields_evaluated TEXT NOT NULL DEFAULT '{}',
            ece                REAL NOT NULL DEFAULT 0.0,
            mce                REAL NOT NULL DEFAULT 0.0,
            calibration_json   TEXT NOT NULL DEFAULT '{}',
            drift_json         TEXT NOT NULL DEFAULT '{}',
            run_at             TEXT NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_er_provider_tag ON eval_runs(provider_tag)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_er_run_at       ON eval_runs(run_at)")

    # -- audit_log --
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            event_id   TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            filing_id  TEXT,
            actor      TEXT NOT NULL DEFAULT 'system',
            payload    TEXT NOT NULL DEFAULT '{}',
            timestamp  TEXT NOT NULL,
            severity   TEXT NOT NULL DEFAULT 'INFO',
            trace_id   TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_al_event_type ON audit_log(event_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_al_filing_id  ON audit_log(filing_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_al_timestamp  ON audit_log(timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_al_severity   ON audit_log(severity)")

    # -- decision_traces --
    op.execute("""
        CREATE TABLE IF NOT EXISTS decision_traces (
            trace_id          TEXT PRIMARY KEY,
            filing_id         TEXT NOT NULL,
            started_at        TEXT NOT NULL,
            finished_at       TEXT NOT NULL DEFAULT '',
            total_duration_ms REAL NOT NULL DEFAULT 0.0,
            total_tokens      INTEGER NOT NULL DEFAULT 0,
            overall_status    TEXT NOT NULL DEFAULT 'ok',
            steps_json        TEXT NOT NULL DEFAULT '[]'
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_dt_filing_id  ON decision_traces(filing_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_dt_started_at ON decision_traces(started_at)")

    # -- citations --
    op.execute("""
        CREATE TABLE IF NOT EXISTS citations (
            filing_id      TEXT PRIMARY KEY,
            source_url     TEXT NOT NULL DEFAULT '',
            citations_json TEXT NOT NULL DEFAULT '[]',
            extracted_at   TEXT NOT NULL
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS citations")
    op.execute("DROP TABLE IF EXISTS decision_traces")
    op.execute("DROP TABLE IF EXISTS audit_log")
    op.execute("DROP TABLE IF EXISTS eval_runs")
    op.execute("DROP TABLE IF EXISTS belief_history")
    op.execute("DROP TABLE IF EXISTS belief_states")
    op.execute("DROP TABLE IF EXISTS feedback_log")
    op.execute("DROP TABLE IF EXISTS entity_relations")
    op.execute("DROP TABLE IF EXISTS memories")
    op.execute("DROP EXTENSION IF EXISTS vector")
