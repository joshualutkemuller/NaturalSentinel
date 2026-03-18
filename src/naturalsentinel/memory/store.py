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
from naturalsentinel.evidence import EvidenceLedgerEntry
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

    def recall_evidence(
        self,
        query: str,
        *,
        top_k: int = 5,
        namespace: str | None = None,
        business_lines: list[str] | None = None,
        candidate_actions: list[str] | None = None,
    ) -> list[EvidenceLedgerEntry]:
        """Rank memory items by decision relevance and return evidence ledger entries."""
        memory_candidates = self.recall(query, top_k=top_k * 3)
        if namespace:
            memory_candidates = [
                rec for rec in memory_candidates
                if rec.namespace in {namespace, "global"}
            ]
        ledger = [
            self._to_evidence_entry(
                rec,
                query=query,
                namespace=namespace,
                business_lines=business_lines or [],
                candidate_actions=candidate_actions or [],
            )
            for rec in memory_candidates
        ]
        ledger.sort(key=lambda item: item.strength_score, reverse=True)
        return ledger[:top_k]

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
        Pulls weighted evidence from episodic memories, entity knowledge, and precedents.
        """
        sections: list[str] = []

        evidence = self.recall_evidence(
            filing_text[:500],
            top_k=5,
            namespace=filing_domain,
        )
        if evidence:
            lines = []
            for item in evidence[:3]:
                lines.append(
                    f"- [{item.evidence_id}] strength={item.strength_score:.2f}, novelty={item.novelty_score:.2f}, "
                    f"supports={'; '.join(item.supports[:2]) or 'n/a'}, contradicts={'; '.join(item.contradicts[:2]) or 'n/a'}"
                )
            sections.append("WEIGHTED EVIDENCE LEDGER:\n" + "\n".join(lines))

        past = self.recall(filing_text[:500], top_k=3, memory_type=MemoryType.EPISODIC, namespace=filing_domain)
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

    def _to_evidence_entry(
        self,
        rec: MemoryRecord,
        *,
        query: str,
        namespace: str | None,
        business_lines: list[str],
        candidate_actions: list[str],
    ) -> EvidenceLedgerEntry:
        source_authority = self._source_authority(rec)
        recency_score = self._recency_score(rec)
        policy_finality_score = self._policy_finality_score(rec)
        jurisdiction_relevance = self._jurisdiction_relevance(rec, query, namespace)
        business_line_proximity = self._business_line_proximity(rec, query, business_lines)
        historical_predictive_usefulness = self._historical_predictive_usefulness(rec)
        contradiction_risk = self._contradiction_risk(rec, query)
        novelty_score = self._novelty_score(rec, query)
        retrieval_score = max(0.0, min(1.0, rec.relevance_score))

        strength_score = (
            0.20 * source_authority
            + 0.15 * recency_score
            + 0.15 * policy_finality_score
            + 0.15 * jurisdiction_relevance
            + 0.15 * business_line_proximity
            + 0.10 * historical_predictive_usefulness
            + 0.10 * retrieval_score
            - 0.10 * contradiction_risk
        )
        strength_score = max(0.0, min(1.0, strength_score))

        supports = self._supports(rec, candidate_actions)
        contradicts = self._contradicts(rec, candidate_actions)
        trace = [
            f"memory_id={rec.id}",
            f"namespace={rec.namespace}",
            f"created_at={rec.created_at}",
            f"updated_at={rec.updated_at}",
        ]

        return EvidenceLedgerEntry(
            evidence_id=rec.id,
            source_type=rec.memory_type.value,
            supports=supports,
            contradicts=contradicts,
            strength_score=round(strength_score, 4),
            novelty_score=round(novelty_score, 4),
            trace=trace,
            source_authority=round(source_authority, 4),
            recency_score=round(recency_score, 4),
            policy_finality_score=round(policy_finality_score, 4),
            jurisdiction_relevance=round(jurisdiction_relevance, 4),
            business_line_proximity=round(business_line_proximity, 4),
            historical_predictive_usefulness=round(historical_predictive_usefulness, 4),
            contradiction_risk=round(contradiction_risk, 4),
            summary=self._summary_for_record(rec),
        )

    def _source_authority(self, rec: MemoryRecord) -> float:
        if rec.memory_type == MemoryType.EPISODIC:
            return 0.9
        if rec.memory_type == MemoryType.PRECEDENT:
            return 0.8
        return 0.65

    def _recency_score(self, rec: MemoryRecord) -> float:
        try:
            age_days = max((datetime.utcnow() - datetime.fromisoformat(rec.updated_at)).days, 0)
        except ValueError:
            return 0.5
        return max(0.1, 1.0 - min(age_days, 365) / 365)

    def _policy_finality_score(self, rec: MemoryRecord) -> float:
        if rec.memory_type != MemoryType.EPISODIC:
            return 0.55
        filing = rec.content.get("filing", {})
        change_type = filing.get("change_type") or rec.content.get("impact", {}).get("change_type")
        scores = {
            "final_rule": 1.0,
            "enforcement": 0.95,
            "guidance": 0.8,
            "amendment": 0.75,
            "executive_order": 0.7,
            "notice": 0.55,
            "proposed_rule": 0.45,
        }
        return scores.get(change_type, 0.55)

    def _jurisdiction_relevance(self, rec: MemoryRecord, query: str, namespace: str | None) -> float:
        q = query.lower()
        if namespace and rec.namespace == namespace:
            return 1.0
        if rec.namespace and rec.namespace in q:
            return 0.8
        if rec.namespace == "global":
            return 0.6
        return 0.4

    def _business_line_proximity(self, rec: MemoryRecord, query: str, business_lines: list[str]) -> float:
        q = query.lower()
        impact = rec.content.get("impact", {})
        filing_lines = {line.lower() for line in impact.get("affected_business_lines", [])}
        requested = {line.lower() for line in business_lines}
        query_hits = {line for line in filing_lines if line in q}
        overlap = filing_lines & requested
        score = 0.2
        if filing_lines:
            score += min(0.5, 0.25 * len(overlap))
            score += min(0.3, 0.15 * len(query_hits))
        return min(1.0, score)

    def _historical_predictive_usefulness(self, rec: MemoryRecord) -> float:
        base = min(1.0, 0.2 + 0.1 * rec.access_count)
        if rec.memory_type == MemoryType.PRECEDENT:
            base = max(base, 0.85)
        return min(1.0, base)

    def _contradiction_risk(self, rec: MemoryRecord, query: str) -> float:
        content_blob = json.dumps(rec.content).lower()
        risk = 0.1
        if rec.memory_type == MemoryType.PRECEDENT:
            risk += 0.35
        contradiction_markers = ["unless", "except", "however", "but", "challenge", "contradict"]
        risk += 0.1 * sum(1 for marker in contradiction_markers if marker in content_blob or marker in query.lower())
        return min(1.0, risk)

    def _novelty_score(self, rec: MemoryRecord, query: str) -> float:
        base = 1.0 - min(rec.access_count, 5) / 5
        if rec.memory_type == MemoryType.PRECEDENT:
            base = max(base, 0.75)
        if rec.namespace and rec.namespace in query.lower():
            base += 0.05
        return max(0.0, min(1.0, base))

    def _supports(self, rec: MemoryRecord, candidate_actions: list[str]) -> list[str]:
        if rec.memory_type == MemoryType.PRECEDENT:
            field = rec.content.get("field", "review")
            return [f"Tightens analyst treatment of {field}"]
        actions = candidate_actions or rec.content.get("impact", {}).get("action_items", [])
        return actions[:2] if actions else ["Supports further review of the current filing"]

    def _contradicts(self, rec: MemoryRecord, candidate_actions: list[str]) -> list[str]:
        if rec.memory_type == MemoryType.PRECEDENT:
            return [f"Challenges prior view on {rec.content.get('field', 'assessment')}"]
        if candidate_actions:
            return [f"May challenge action: {candidate_actions[0]}"] if rec.relevance_score < 0.35 else []
        return []

    def _summary_for_record(self, rec: MemoryRecord) -> str:
        if rec.memory_type == MemoryType.EPISODIC:
            filing = rec.content.get("filing", {})
            impact = rec.content.get("impact", {})
            return f"{filing.get('title', rec.key)} | severity={impact.get('severity', '?')}"
        if rec.memory_type == MemoryType.PRECEDENT:
            return f"Feedback precedent on {rec.content.get('filing_id', rec.key)}.{rec.content.get('field', '?')}"
        return f"Entity memory for {rec.key}"

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
