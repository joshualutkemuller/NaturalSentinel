"""
memory.py — Persistent Memory System for the Regulatory Monitor Agent
=====================================================================

Provides three memory types that make the agent smarter over time:

1. EPISODIC MEMORY  — Full record of every filing + analysis the agent has processed.
   Used to detect patterns ("this agency tends to finalize proposed rules within 6 months"),
   recall prior assessments, and avoid redundant work.

2. ENTITY MEMORY — Knowledge about specific regulations, agencies, business lines,
   and their relationships. Builds a growing graph of "Regulation S-K affects ESG,
   Corporate Finance…" that improves impact mapping over time.

3. PRECEDENT MEMORY — Stores correction/feedback signals. When a human says
   "that severity should have been HIGH, not MEDIUM", the agent records the
   correction and injects relevant precedents into future prompts so it
   self-corrects over time.

All three are backed by SQLite for zero-dependency persistence.
Semantic similarity search is supported via TF-IDF when scikit-learn is
available, falling back to keyword overlap otherwise.
"""

import hashlib
import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger("RegMemory")

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class MemoryType(Enum):
    EPISODIC = "episodic"  # Full filing + analysis records
    ENTITY = "entity"  # Knowledge about regs, agencies, biz lines
    PRECEDENT = "precedent"  # Correction / feedback signals


@dataclass
class MemoryRecord:
    id: str
    memory_type: MemoryType
    namespace: str  # e.g. "sec", "cfpb", or "global"
    key: str  # Filing ID, entity name, or precedent label
    content: dict  # Arbitrary JSON payload
    embedding_text: str  # Text used for similarity search
    created_at: str
    updated_at: str
    access_count: int = 0
    relevance_score: float = 1.0  # Decays over time, boosted on access


# ---------------------------------------------------------------------------
# Lightweight similarity engine (no heavy deps required)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _keyword_similarity(query_tokens: list[str], doc_tokens: list[str]) -> float:
    """Jaccard-like overlap with IDF weighting."""
    if not query_tokens or not doc_tokens:
        return 0.0
    q_set = set(query_tokens)
    d_set = set(doc_tokens)
    intersection = q_set & d_set
    if not intersection:
        return 0.0
    # Weight longer shared tokens more heavily
    score = sum(len(t) for t in intersection)
    normalizer = sum(len(t) for t in q_set | d_set)
    return score / normalizer if normalizer else 0.0


class SimilarityEngine:
    """
    Attempts to use sklearn TF-IDF for real cosine similarity.
    Falls back to keyword overlap if sklearn is unavailable.
    """

    def __init__(self):
        self._use_sklearn = False
        self._vectorizer = None
        self._matrix = None
        self._doc_ids: list[str] = []
        self._doc_tokens: dict[str, list[str]] = {}
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            self._vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
            self._cosine_similarity = cosine_similarity
            self._use_sklearn = True
            logger.info("SimilarityEngine: using sklearn TF-IDF")
        except ImportError:
            logger.info("SimilarityEngine: sklearn not found, using keyword fallback")

    def index(self, documents: dict[str, str]):
        """Index a batch of {id: text} documents."""
        self._doc_ids = list(documents.keys())
        texts = list(documents.values())

        if self._use_sklearn and texts:
            self._matrix = self._vectorizer.fit_transform(texts)
        else:
            self._doc_tokens = {did: _tokenize(text) for did, text in documents.items()}

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """Return [(doc_id, score), ...] sorted by descending similarity."""
        if not self._doc_ids:
            return []

        if self._use_sklearn and self._matrix is not None:
            q_vec = self._vectorizer.transform([query])
            scores = self._cosine_similarity(q_vec, self._matrix).flatten()
            ranked = sorted(zip(self._doc_ids, scores), key=lambda x: x[1], reverse=True)
            return ranked[:top_k]
        else:
            q_tokens = _tokenize(query)
            scored = [
                (did, _keyword_similarity(q_tokens, tokens))
                for did, tokens in self._doc_tokens.items()
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:top_k]


# ---------------------------------------------------------------------------
# Core memory store
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id           TEXT PRIMARY KEY,
    memory_type  TEXT NOT NULL,
    namespace    TEXT NOT NULL,
    key          TEXT NOT NULL,
    content      TEXT NOT NULL,
    embedding_text TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    access_count INTEGER DEFAULT 0,
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


class MemoryStore:
    """
    SQLite-backed persistent memory with similarity search.

    Usage:
        mem = MemoryStore("./regmon_memory.db")
        mem.store_episodic(filing_id, filing_dict, impact_dict)
        mem.store_entity("Regulation S-K", {...})
        mem.record_feedback("SEC-2026-0312-A", "severity", "medium", "critical", "has enforcement teeth")
        relevant = mem.recall("climate disclosure SEC", top_k=3)
    """

    def __init__(self, db_path: str = "regmon_memory.db"):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()
        self.similarity = SimilarityEngine()
        self._rebuild_index()
        logger.info("MemoryStore initialized: %s (%d records)", db_path, self.count())

    def close(self):
        self.conn.close()

    # -- Counts & stats -----------------------------------------------------

    def count(self, memory_type: MemoryType | None = None) -> int:
        if memory_type:
            row = self.conn.execute(
                "SELECT COUNT(*) FROM memories WHERE memory_type = ?", (memory_type.value,)
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) FROM memories").fetchone()
        return row[0]

    def stats(self) -> dict:
        """Return summary statistics about the memory store."""
        total = self.count()
        by_type = {}
        for mt in MemoryType:
            by_type[mt.value] = self.count(mt)
        by_ns = {}
        for row in self.conn.execute(
            "SELECT namespace, COUNT(*) as c FROM memories GROUP BY namespace"
        ):
            by_ns[row["namespace"]] = row["c"]
        feedback_count = self.conn.execute("SELECT COUNT(*) FROM feedback_log").fetchone()[0]
        relation_count = self.conn.execute("SELECT COUNT(*) FROM entity_relations").fetchone()[0]
        return {
            "total_memories": total,
            "by_type": by_type,
            "by_namespace": by_ns,
            "total_feedback": feedback_count,
            "total_relations": relation_count,
            "db_path": str(self.db_path),
        }

    # -- Storage ------------------------------------------------------------

    def _upsert(self, record: MemoryRecord):
        self.conn.execute(
            """
            INSERT INTO memories (id, memory_type, namespace, key, content,
                                  embedding_text, created_at, updated_at,
                                  access_count, relevance_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                content = excluded.content,
                embedding_text = excluded.embedding_text,
                updated_at = excluded.updated_at,
                access_count = access_count + 1
        """,
            (
                record.id,
                record.memory_type.value,
                record.namespace,
                record.key,
                json.dumps(record.content),
                record.embedding_text,
                record.created_at,
                record.updated_at,
                record.access_count,
                record.relevance_score,
            ),
        )
        self.conn.commit()
        self._rebuild_index()

    def store_episodic(self, filing_id: str, filing: dict, impact: dict):
        """Store a complete filing + analysis as episodic memory."""
        now = datetime.utcnow().isoformat()
        embed_text = " ".join(
            [
                filing.get("title", ""),
                filing.get("summary", ""),
                filing.get("domain", ""),
                impact.get("risk_summary", ""),
                " ".join(impact.get("affected_business_lines", [])),
                " ".join(impact.get("affected_regulations", [])),
            ]
        )
        record = MemoryRecord(
            id=f"episodic:{filing_id}",
            memory_type=MemoryType.EPISODIC,
            namespace=filing.get("domain", "global"),
            key=filing_id,
            content={"filing": filing, "impact": impact},
            embedding_text=embed_text,
            created_at=now,
            updated_at=now,
        )
        self._upsert(record)

        # Auto-extract entity relations from impact data
        for biz_line in impact.get("affected_business_lines", []):
            self._add_relation(filing_id, "affects_business", biz_line, filing_id)
        for reg in impact.get("affected_regulations", []):
            self._add_relation(filing_id, "modifies_regulation", reg, filing_id)
            # Also link regulation to business lines
            for biz_line in impact.get("affected_business_lines", []):
                self._add_relation(reg, "impacts", biz_line, filing_id)

        logger.debug("Stored episodic memory: %s", filing_id)

    def store_entity(self, entity_name: str, attributes: dict, namespace: str = "global"):
        """Store or update knowledge about a specific entity (regulation, agency, etc.)."""
        now = datetime.utcnow().isoformat()
        eid = f"entity:{hashlib.sha256(entity_name.encode()).hexdigest()[:16]}"
        embed_text = f"{entity_name} " + " ".join(
            f"{k}: {v}" for k, v in attributes.items() if isinstance(v, str)
        )
        record = MemoryRecord(
            id=eid,
            memory_type=MemoryType.ENTITY,
            namespace=namespace,
            key=entity_name,
            content=attributes,
            embedding_text=embed_text,
            created_at=now,
            updated_at=now,
        )
        self._upsert(record)

    def record_feedback(
        self, filing_id: str, field: str, old_value: str, new_value: str, reason: str = ""
    ):
        """
        Record a human correction. This creates both a feedback log entry
        and a precedent memory that future analyses can learn from.
        """
        now = datetime.utcnow().isoformat()

        # Log the raw correction
        self.conn.execute(
            """
            INSERT INTO feedback_log (filing_id, field, old_value, new_value, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (filing_id, field, old_value, new_value, reason, now),
        )

        # Create a precedent memory
        pid = f"precedent:{filing_id}:{field}:{hashlib.sha256(now.encode()).hexdigest()[:8]}"
        # Pull the original episodic memory for context
        episodic = self.get(f"episodic:{filing_id}")
        context_text = ""
        if episodic:
            f = episodic.content.get("filing", {})
            context_text = f"{f.get('title', '')} {f.get('domain', '')} {f.get('summary', '')}"

        embed_text = (
            f"correction {field} from {old_value} to {new_value} "
            f"reason: {reason} context: {context_text}"
        )
        record = MemoryRecord(
            id=pid,
            memory_type=MemoryType.PRECEDENT,
            namespace="global",
            key=f"{filing_id}:{field}",
            content={
                "filing_id": filing_id,
                "field": field,
                "old_value": old_value,
                "new_value": new_value,
                "reason": reason,
                "context_snippet": context_text[:300],
            },
            embedding_text=embed_text,
            created_at=now,
            updated_at=now,
        )
        self._upsert(record)
        self.conn.commit()
        logger.info("Recorded feedback for %s.%s: %s → %s", filing_id, field, old_value, new_value)

    # -- Retrieval ----------------------------------------------------------

    def get(self, memory_id: str) -> MemoryRecord | None:
        """Retrieve a specific memory by ID."""
        row = self.conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if not row:
            return None
        # Bump access count
        self.conn.execute(
            "UPDATE memories SET access_count = access_count + 1 WHERE id = ?", (memory_id,)
        )
        self.conn.commit()
        return self._row_to_record(row)

    def recall(
        self,
        query: str,
        top_k: int = 5,
        memory_type: MemoryType | None = None,
        namespace: str | None = None,
    ) -> list[MemoryRecord]:
        """
        Semantic recall — find the most relevant memories for a query.
        Optionally filter by type and namespace.
        """
        candidates = self.similarity.search(query, top_k=top_k * 3)

        results = []
        for doc_id, score in candidates:
            if score <= 0:
                continue
            row = self.conn.execute("SELECT * FROM memories WHERE id = ?", (doc_id,)).fetchone()
            if not row:
                continue
            if memory_type and row["memory_type"] != memory_type.value:
                continue
            if namespace and row["namespace"] != namespace:
                continue
            rec = self._row_to_record(row)
            rec.relevance_score = score
            results.append(rec)
            if len(results) >= top_k:
                break

        return results

    def get_related_entities(self, entity_name: str) -> list[dict]:
        """Get all entities related to a given entity via the relation graph."""
        rows = self.conn.execute(
            """
            SELECT * FROM entity_relations
            WHERE source = ? OR target = ?
            ORDER BY weight DESC
        """,
            (entity_name, entity_name),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_precedents_for_domain(self, domain: str, top_k: int = 5) -> list[MemoryRecord]:
        """Get correction precedents relevant to a specific regulatory domain."""
        return self.recall(
            query=f"{domain} regulatory correction precedent",
            top_k=top_k,
            memory_type=MemoryType.PRECEDENT,
        )

    def get_filing_history(self, domain: str | None = None, limit: int = 20) -> list[MemoryRecord]:
        """Retrieve recent episodic memories, optionally filtered by domain."""
        if domain:
            rows = self.conn.execute(
                """
                SELECT * FROM memories
                WHERE memory_type = 'episodic' AND namespace = ?
                ORDER BY created_at DESC LIMIT ?
            """,
                (domain, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT * FROM memories
                WHERE memory_type = 'episodic'
                ORDER BY created_at DESC LIMIT ?
            """,
                (limit,),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    # -- Context builder for LLM prompts ------------------------------------

    def build_context_block(
        self, filing_domain: str, filing_text: str, max_tokens: int = 1500
    ) -> str:
        """
        Build a memory context block to inject into the LLM prompt.
        Pulls relevant episodic memories, entity knowledge, and precedents.

        This is the key integration point — the agent becomes smarter because
        each analysis is informed by everything it has seen before.
        """
        sections = []

        # 1. Relevant past analyses
        past = self.recall(filing_text[:500], top_k=3, memory_type=MemoryType.EPISODIC)
        if past:
            lines = []
            for rec in past:
                imp = rec.content.get("impact", {})
                fil = rec.content.get("filing", {})
                lines.append(
                    f"- [{fil.get('id', '?')}] {fil.get('title', '?')} → "
                    f"severity={imp.get('severity', '?')}, "
                    f"lines={','.join(imp.get('affected_business_lines', [])[:3])}"
                )
            sections.append("RELEVANT PAST ANALYSES:\n" + "\n".join(lines))

        # 2. Precedent corrections
        precs = self.get_precedents_for_domain(filing_domain, top_k=3)
        if precs:
            lines = []
            for rec in precs:
                c = rec.content
                lines.append(
                    f"- Correction on {c.get('filing_id', '?')}.{c.get('field', '?')}: "
                    f"{c.get('old_value', '?')} → {c.get('new_value', '?')} "
                    f"(reason: {c.get('reason', 'n/a')})"
                )
            sections.append("CORRECTION PRECEDENTS (learn from these):\n" + "\n".join(lines))

        # 3. Entity knowledge
        entities = self.recall(filing_text[:300], top_k=3, memory_type=MemoryType.ENTITY)
        if entities:
            lines = []
            for rec in entities:
                lines.append(f"- {rec.key}: {json.dumps(rec.content)[:200]}")
            sections.append("KNOWN ENTITIES:\n" + "\n".join(lines))

        if not sections:
            return ""

        block = "\n\n".join(sections)
        # Rough token truncation (4 chars ≈ 1 token)
        if len(block) > max_tokens * 4:
            block = block[: max_tokens * 4] + "\n[…truncated]"

        return f"\n--- AGENT MEMORY CONTEXT ---\n{block}\n--- END MEMORY CONTEXT ---\n"

    # -- Internals ----------------------------------------------------------

    def _add_relation(self, source: str, relation: str, target: str, context: str = ""):
        """Add or strengthen an entity relation edge."""
        self.conn.execute(
            """
            INSERT INTO entity_relations (source, relation, target, weight, context, created_at)
            VALUES (?, ?, ?, 1.0, ?, ?)
            ON CONFLICT(source, relation, target) DO UPDATE SET
                weight = weight + 0.5,
                context = excluded.context
        """,
            (source, relation, target, context, datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def _rebuild_index(self):
        """Rebuild the similarity search index from all stored memories."""
        rows = self.conn.execute("SELECT id, embedding_text FROM memories").fetchall()
        if rows:
            docs = {row["id"]: row["embedding_text"] for row in rows}
            self.similarity.index(docs)

    def _row_to_record(self, row) -> MemoryRecord:
        return MemoryRecord(
            id=row["id"],
            memory_type=MemoryType(row["memory_type"]),
            namespace=row["namespace"],
            key=row["key"],
            content=json.loads(row["content"]),
            embedding_text=row["embedding_text"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            access_count=row["access_count"],
            relevance_score=row["relevance_score"],
        )

    # -- Cleanup ------------------------------------------------------------

    def prune(self, older_than_days: int = 365, min_access: int = 0):
        """Remove old, low-access memories to keep the store lean."""
        cutoff = datetime(datetime.utcnow().year, datetime.utcnow().month, datetime.utcnow().day)
        from datetime import timedelta

        cutoff = (cutoff - timedelta(days=older_than_days)).isoformat()
        deleted = self.conn.execute(
            """
            DELETE FROM memories
            WHERE created_at < ? AND access_count <= ?
            AND memory_type != 'precedent'
        """,
            (cutoff, min_access),
        ).rowcount
        self.conn.commit()
        self._rebuild_index()
        logger.info("Pruned %d old memories", deleted)
        return deleted

    def export_json(self) -> str:
        """Export all memories as JSON for backup/migration."""
        rows = self.conn.execute("SELECT * FROM memories ORDER BY created_at").fetchall()
        records = [dict(r) for r in rows]
        relations = [
            dict(r) for r in self.conn.execute("SELECT * FROM entity_relations").fetchall()
        ]
        feedback = [dict(r) for r in self.conn.execute("SELECT * FROM feedback_log").fetchall()]
        return json.dumps(
            {
                "memories": records,
                "relations": relations,
                "feedback": feedback,
                "exported_at": datetime.utcnow().isoformat(),
            },
            indent=2,
        )

    def import_json(self, data: str):
        """Import memories from a JSON export."""
        payload = json.loads(data)
        for rec in payload.get("memories", []):
            self.conn.execute(
                """
                INSERT OR REPLACE INTO memories
                (id, memory_type, namespace, key, content, embedding_text,
                 created_at, updated_at, access_count, relevance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    rec["id"],
                    rec["memory_type"],
                    rec["namespace"],
                    rec["key"],
                    rec["content"],
                    rec["embedding_text"],
                    rec["created_at"],
                    rec["updated_at"],
                    rec["access_count"],
                    rec["relevance_score"],
                ),
            )
        self.conn.commit()
        self._rebuild_index()
        logger.info("Imported %d memories", len(payload.get("memories", [])))
