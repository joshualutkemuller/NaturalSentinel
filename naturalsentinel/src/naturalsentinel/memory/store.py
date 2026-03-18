"""SQLite-backed persistent memory store with semantic search."""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from naturalsentinel.memory.schema import SCHEMA_SQL
from naturalsentinel.memory.similarity import SimilarityEngine
from naturalsentinel.memory.types import MemoryRecord, MemoryType

logger = logging.getLogger(__name__)


class MemoryStore:
    """
    Persistent memory with three types: episodic, entity, and precedent.

    Usage::

        mem = MemoryStore("./naturalsentinel_memory.db")      # file-backed
        mem = MemoryStore(":memory:")                 # in-memory for tests

        mem.store_episodic(filing_id, filing_dict, impact_dict)
        mem.store_entity("Regulation S-K", {...})
        mem.record_feedback("SEC-2026-0312-A", "severity", "medium", "critical", "reason")
        results = mem.recall("climate disclosure SEC", top_k=3)
    """

    def __init__(self, db_path: str = "naturalsentinel_memory.db"):
        self.db_path = Path(db_path) if db_path != ":memory:" else db_path
        self.conn = sqlite3.connect(
            str(self.db_path) if isinstance(self.db_path, Path) else self.db_path,
            check_same_thread=False,
        )
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()
        self.similarity = SimilarityEngine()
        self._rebuild_index()
        logger.debug("MemoryStore initialized: %s (%d records)", db_path, self.count())

    def close(self):
        self.conn.close()

    # -- Counts & stats -----------------------------------------------------

    def count(self, memory_type: MemoryType | None = None) -> int:
        if memory_type:
            row = self.conn.execute(
                "SELECT COUNT(*) FROM memories WHERE memory_type = ?",
                (memory_type.value,),
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) FROM memories").fetchone()
        return row[0]

    def stats(self) -> dict:
        """Summary statistics about the memory store."""
        by_type = {mt.value: self.count(mt) for mt in MemoryType}
        by_ns = {}
        for row in self.conn.execute(
            "SELECT namespace, COUNT(*) as c FROM memories GROUP BY namespace"
        ):
            by_ns[row["namespace"]] = row["c"]
        return {
            "total_memories": self.count(),
            "by_type": by_type,
            "by_namespace": by_ns,
            "total_feedback": self.conn.execute("SELECT COUNT(*) FROM feedback_log").fetchone()[0],
            "total_relations": self.conn.execute(
                "SELECT COUNT(*) FROM entity_relations"
            ).fetchone()[0],
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
        self._upsert(
            MemoryRecord(
                id=f"episodic:{filing_id}",
                memory_type=MemoryType.EPISODIC,
                namespace=filing.get("domain", "global"),
                key=filing_id,
                content={"filing": filing, "impact": impact},
                embedding_text=embed_text,
                created_at=now,
                updated_at=now,
            )
        )
        # Auto-extract entity relations
        for biz_line in impact.get("affected_business_lines", []):
            self._add_relation(filing_id, "affects_business", biz_line, filing_id)
        for reg in impact.get("affected_regulations", []):
            self._add_relation(filing_id, "modifies_regulation", reg, filing_id)
            for biz_line in impact.get("affected_business_lines", []):
                self._add_relation(reg, "impacts", biz_line, filing_id)

    def store_entity(self, entity_name: str, attributes: dict, namespace: str = "global"):
        """Store or update knowledge about a specific entity."""
        now = datetime.utcnow().isoformat()
        eid = f"entity:{hashlib.sha256(entity_name.encode()).hexdigest()[:16]}"
        embed_text = f"{entity_name} " + " ".join(
            f"{k}: {v}" for k, v in attributes.items() if isinstance(v, str)
        )
        self._upsert(
            MemoryRecord(
                id=eid,
                memory_type=MemoryType.ENTITY,
                namespace=namespace,
                key=entity_name,
                content=attributes,
                embedding_text=embed_text,
                created_at=now,
                updated_at=now,
            )
        )

    def record_feedback(
        self,
        filing_id: str,
        field: str,
        old_value: str,
        new_value: str,
        reason: str = "",
    ):
        """Record a human correction → creates a feedback log + precedent memory."""
        now = datetime.utcnow().isoformat()

        self.conn.execute(
            "INSERT INTO feedback_log (filing_id, field, old_value, new_value, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (filing_id, field, old_value, new_value, reason, now),
        )

        pid = f"precedent:{filing_id}:{field}:{hashlib.sha256(now.encode()).hexdigest()[:8]}"
        episodic = self.get(f"episodic:{filing_id}")
        context_text = ""
        if episodic:
            f = episodic.content.get("filing", {})
            context_text = f"{f.get('title', '')} {f.get('domain', '')} {f.get('summary', '')}"

        embed_text = (
            f"correction {field} from {old_value} to {new_value} "
            f"reason: {reason} context: {context_text}"
        )
        self._upsert(
            MemoryRecord(
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
        )
        self.conn.commit()
        logger.info("Recorded feedback for %s.%s: %s → %s", filing_id, field, old_value, new_value)

    # -- Retrieval ----------------------------------------------------------

    def get(self, memory_id: str) -> Optional[MemoryRecord]:
        """Retrieve a specific memory by ID."""
        row = self.conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if not row:
            return None
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
        """Semantic recall — find the most relevant memories for a query."""
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
            "SELECT * FROM entity_relations WHERE source = ? OR target = ? ORDER BY weight DESC",
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

    def get_filing_history(
        self, domain: str | None = None, limit: int = 20
    ) -> list[MemoryRecord]:
        """Retrieve recent episodic memories, optionally filtered by domain."""
        if domain:
            rows = self.conn.execute(
                "SELECT * FROM memories WHERE memory_type = 'episodic' AND namespace = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (domain, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM memories WHERE memory_type = 'episodic' "
                "ORDER BY created_at DESC LIMIT ?",
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
        """
        sections: list[str] = []

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
            lines = [f"- {rec.key}: {json.dumps(rec.content)[:200]}" for rec in entities]
            sections.append("KNOWN ENTITIES:\n" + "\n".join(lines))

        if not sections:
            return ""

        block = "\n\n".join(sections)
        if len(block) > max_tokens * 4:
            block = block[: max_tokens * 4] + "\n[…truncated]"

        return f"\n--- AGENT MEMORY CONTEXT ---\n{block}\n--- END MEMORY CONTEXT ---\n"

    # -- Internals ----------------------------------------------------------

    def _add_relation(self, source: str, relation: str, target: str, context: str = ""):
        self.conn.execute(
            """
            INSERT INTO entity_relations (source, relation, target, weight, context, created_at)
            VALUES (?, ?, ?, 1.0, ?, ?)
            ON CONFLICT(source, relation, target) DO UPDATE SET
                weight = weight + 0.5, context = excluded.context
            """,
            (source, relation, target, context, datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def _rebuild_index(self):
        rows = self.conn.execute("SELECT id, embedding_text FROM memories").fetchall()
        if rows:
            self.similarity.index({row["id"]: row["embedding_text"] for row in rows})

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

    # -- Maintenance --------------------------------------------------------

    def prune(self, older_than_days: int = 365, min_access: int = 0) -> int:
        """Remove old, low-access memories (never prunes precedents)."""
        cutoff = (datetime.utcnow() - timedelta(days=older_than_days)).isoformat()
        deleted = self.conn.execute(
            "DELETE FROM memories WHERE created_at < ? AND access_count <= ? "
            "AND memory_type != 'precedent'",
            (cutoff, min_access),
        ).rowcount
        self.conn.commit()
        self._rebuild_index()
        return deleted

    def export_json(self) -> str:
        """Export all memories as JSON for backup/migration."""
        return json.dumps(
            {
                "memories": [dict(r) for r in self.conn.execute("SELECT * FROM memories ORDER BY created_at")],
                "relations": [dict(r) for r in self.conn.execute("SELECT * FROM entity_relations")],
                "feedback": [dict(r) for r in self.conn.execute("SELECT * FROM feedback_log")],
                "exported_at": datetime.utcnow().isoformat(),
            },
            indent=2,
        )

    def import_json(self, data: str):
        """Import memories from a JSON export."""
        payload = json.loads(data)
        for rec in payload.get("memories", []):
            self.conn.execute(
                "INSERT OR REPLACE INTO memories "
                "(id, memory_type, namespace, key, content, embedding_text, "
                "created_at, updated_at, access_count, relevance_score) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rec["id"], rec["memory_type"], rec["namespace"], rec["key"],
                    rec["content"], rec["embedding_text"], rec["created_at"],
                    rec["updated_at"], rec["access_count"], rec["relevance_score"],
                ),
            )
        self.conn.commit()
        self._rebuild_index()
