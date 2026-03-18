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
"""
