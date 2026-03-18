"""SQLite schema for the memory store."""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id             TEXT PRIMARY KEY,
    memory_type    TEXT NOT NULL,
    namespace      TEXT NOT NULL,
    key            TEXT NOT NULL,
    content        TEXT NOT NULL,
    embedding_text TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    access_count   INTEGER DEFAULT 0,
    relevance_score REAL DEFAULT 1.0
);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_ns   ON memories(namespace);
CREATE INDEX IF NOT EXISTS idx_memories_key  ON memories(key);

CREATE TABLE IF NOT EXISTS entity_relations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source     TEXT NOT NULL,
    relation   TEXT NOT NULL,
    target     TEXT NOT NULL,
    weight     REAL DEFAULT 1.0,
    context    TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(source, relation, target)
);

CREATE INDEX IF NOT EXISTS idx_er_source ON entity_relations(source);
CREATE INDEX IF NOT EXISTS idx_er_target ON entity_relations(target);

CREATE TABLE IF NOT EXISTS feedback_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filing_id   TEXT NOT NULL,
    field       TEXT NOT NULL,
    old_value   TEXT,
    new_value   TEXT,
    reason      TEXT,
    created_at  TEXT NOT NULL
);

-- Priority 3: prior/posterior belief tracking per topic
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
);

-- Full history of every confidence observation for a (topic, domain) pair
CREATE TABLE IF NOT EXISTS belief_history (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    topic            TEXT NOT NULL,
    domain           TEXT NOT NULL,
    confidence       REAL NOT NULL,
    delta_confidence REAL NOT NULL,
    delta_drivers    TEXT NOT NULL DEFAULT '[]',
    filing_id        TEXT NOT NULL DEFAULT '',
    observed_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bh_topic_domain ON belief_history(topic, domain);
CREATE INDEX IF NOT EXISTS idx_bs_domain        ON belief_states(domain);

-- Quantitative evaluation run results
CREATE TABLE IF NOT EXISTS eval_runs (
    run_id               TEXT PRIMARY KEY,
    provider_tag         TEXT NOT NULL DEFAULT 'default',
    suite_name           TEXT NOT NULL DEFAULT 'feedback_log',
    n_cases              INTEGER NOT NULL DEFAULT 0,
    overall_accuracy     REAL NOT NULL DEFAULT 0.0,
    per_field_accuracy   TEXT NOT NULL DEFAULT '{}',
    domain_breakdown     TEXT NOT NULL DEFAULT '{}',
    n_fields_evaluated   TEXT NOT NULL DEFAULT '{}',
    ece                  REAL NOT NULL DEFAULT 0.0,
    mce                  REAL NOT NULL DEFAULT 0.0,
    calibration_json     TEXT NOT NULL DEFAULT '{}',
    drift_json           TEXT NOT NULL DEFAULT '{}',
    run_at               TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_er_provider_tag ON eval_runs(provider_tag);
CREATE INDEX IF NOT EXISTS idx_er_run_at       ON eval_runs(run_at);
"""
