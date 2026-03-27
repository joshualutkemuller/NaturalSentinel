"""PostgreSQL-backed memory store.

Replicates the public interface of :class:`~app.naturalsentinel.memory.store.MemoryStore`
using a SQLModel session instead of sqlite3. The embedding_text column is stored as plain
text; semantic recall uses token-overlap scoring.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from sqlmodel import Session, select

from app.naturalsentinel.memory.pg_models import (
    PgBeliefHistory,
    PgBeliefState,
    PgEntityRelation,
    PgFeedbackLog,
    PgMemory,
)
from app.naturalsentinel.memory.types import MemoryRecord, MemoryType

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _score(query: str, embedding_text: str) -> float:
    """Token-overlap similarity — replaced by pgvector once embeddings are wired."""
    q_tokens = set(query.lower().split())
    e_tokens = set(embedding_text.lower().split())
    if not q_tokens or not e_tokens:
        return 0.0
    return len(q_tokens & e_tokens) / len(q_tokens | e_tokens)


class PgMemoryStore:
    """
    PostgreSQL-backed memory store with the same interface as :class:`MemoryStore`.

    Usage::

        # In FastAPI via dependency injection:
        store = PgMemoryStore(session)
        store.store_episodic(filing_id, filing_dict, impact_dict)
        results = store.recall("climate disclosure SEC", top_k=3)
    """

    def __init__(self, session: Session):
        self.session = session

    # -- Counts & stats -------------------------------------------------------

    def count(self, memory_type: MemoryType | None = None) -> int:
        stmt = select(PgMemory)
        if memory_type:
            stmt = stmt.where(PgMemory.memory_type == memory_type.value)
        return len(self.session.exec(stmt).all())

    def stats(self) -> dict:
        all_memories = self.session.exec(select(PgMemory)).all()
        by_type: dict[str, int] = {}
        by_ns: dict[str, int] = {}
        for m in all_memories:
            by_type[m.memory_type] = by_type.get(m.memory_type, 0) + 1
            by_ns[m.namespace] = by_ns.get(m.namespace, 0) + 1
        feedback_count = len(self.session.exec(select(PgFeedbackLog)).all())
        relation_count = len(self.session.exec(select(PgEntityRelation)).all())
        return {
            "total_memories": len(all_memories),
            "by_type": by_type,
            "by_namespace": by_ns,
            "total_feedback": feedback_count,
            "total_relations": relation_count,
            "db_path": "postgresql",
        }

    # -- Internal helpers -----------------------------------------------------

    def _upsert(self, record: MemoryRecord) -> None:
        existing = self.session.get(PgMemory, record.id)
        now = _now()
        if existing:
            existing.content = record.content
            existing.embedding_text = record.embedding_text
            existing.updated_at = now
            existing.access_count = (existing.access_count or 0) + 1
            self.session.add(existing)
        else:
            pg_mem = PgMemory(
                id=record.id,
                memory_type=record.memory_type.value,
                namespace=record.namespace,
                key=record.key,
                content=record.content,
                embedding_text=record.embedding_text,
                created_at=now,
                updated_at=now,
                access_count=record.access_count,
                relevance_score=record.relevance_score,
            )
            self.session.add(pg_mem)
        self.session.commit()

    def _add_relation(
        self, source: str, relation: str, target: str, context: str = ""
    ) -> None:
        stmt = select(PgEntityRelation).where(
            PgEntityRelation.source == source,
            PgEntityRelation.relation == relation,
            PgEntityRelation.target == target,
        )
        existing = self.session.exec(stmt).first()
        if existing:
            existing.weight = (existing.weight or 1.0) + 0.1
            existing.context = context
            self.session.add(existing)
        else:
            rel = PgEntityRelation(
                source=source,
                relation=relation,
                target=target,
                context=context,
                created_at=_now(),
            )
            self.session.add(rel)
        self.session.commit()

    # -- Storage --------------------------------------------------------------

    def store_episodic(self, filing_id: str, filing: dict, impact: dict) -> None:
        """Store a complete filing + analysis as episodic memory."""
        now = _now().isoformat()
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

    def store_entity(
        self, entity_name: str, attributes: dict, namespace: str = "global"
    ) -> None:
        """Store or update knowledge about a specific entity."""
        now = _now().isoformat()
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
    ) -> None:
        """Record a human correction → creates a feedback log + precedent memory."""
        now = _now()
        log_entry = PgFeedbackLog(
            filing_id=filing_id,
            field=field,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            created_at=now,
        )
        self.session.add(log_entry)
        self.session.commit()

        pid = f"precedent:{filing_id}:{field}:{hashlib.sha256(now.isoformat().encode()).hexdigest()[:8]}"
        episodic = self.get(f"episodic:{filing_id}")
        context_text = ""
        if episodic:
            f = episodic.content.get("filing", {})
            context_text = (
                f"{f.get('title', '')} {f.get('domain', '')} {f.get('summary', '')}"
            )

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
                },
                embedding_text=embed_text,
                created_at=now.isoformat(),
                updated_at=now.isoformat(),
            )
        )

    # -- Retrieval ------------------------------------------------------------

    def get(self, memory_id: str) -> MemoryRecord | None:
        """Retrieve a memory record by its exact ID."""
        pg_mem = self.session.get(PgMemory, memory_id)
        if not pg_mem:
            return None
        return self._to_record(pg_mem)

    def recall(self, query: str, top_k: int = 3) -> list[MemoryRecord]:
        """Semantic search — returns top_k most relevant memories for query.

        Uses token-overlap similarity. Replace with pgvector cosine similarity
        once an embedding provider is wired::

            ORDER BY embedding <=> :query_vec LIMIT :top_k
        """
        all_mems = self.session.exec(select(PgMemory)).all()
        scored = sorted(
            [(m, _score(query, m.embedding_text or "")) for m in all_mems],
            key=lambda x: x[1],
            reverse=True,
        )
        results = []
        for pg_mem, score in scored[:top_k]:
            rec = self._to_record(pg_mem)
            rec.relevance_score = score
            results.append(rec)
            # Update access count
            pg_mem.access_count = (pg_mem.access_count or 0) + 1
            self.session.add(pg_mem)
        if results:
            self.session.commit()
        return results

    def get_entity_relations(
        self, source: str | None = None, target: str | None = None
    ) -> list[dict]:
        """Return entity relations filtered by source or target."""
        stmt = select(PgEntityRelation)
        if source:
            stmt = stmt.where(PgEntityRelation.source == source)
        if target:
            stmt = stmt.where(PgEntityRelation.target == target)
        return [
            {
                "source": r.source,
                "relation": r.relation,
                "target": r.target,
                "weight": r.weight,
                "context": r.context,
            }
            for r in self.session.exec(stmt).all()
        ]

    def list_by_type(
        self, memory_type: MemoryType, limit: int = 50
    ) -> list[MemoryRecord]:
        """Return memories of a given type, most recently updated first."""
        stmt = (
            select(PgMemory)
            .where(PgMemory.memory_type == memory_type.value)
            .order_by(PgMemory.updated_at.desc())  # type: ignore[arg-type]
            .limit(limit)
        )
        return [self._to_record(m) for m in self.session.exec(stmt).all()]

    # -- Belief states --------------------------------------------------------

    def get_belief_states(self, domain: str | None = None) -> list[dict]:
        stmt = select(PgBeliefState)
        if domain:
            stmt = stmt.where(PgBeliefState.domain == domain)
        return [
            {
                "topic": b.topic,
                "domain": b.domain,
                "prior_confidence": b.prior_confidence,
                "posterior_confidence": b.posterior_confidence,
                "delta_confidence": b.delta_confidence,
                "stability_score": b.stability_score,
                "observation_count": b.observation_count,
            }
            for b in self.session.exec(stmt).all()
        ]

    def get_belief_history(self, topic: str, domain: str) -> list[dict]:
        stmt = (
            select(PgBeliefHistory)
            .where(PgBeliefHistory.topic == topic, PgBeliefHistory.domain == domain)
            .order_by(PgBeliefHistory.observed_at.desc())  # type: ignore[arg-type]
        )
        return [
            {
                "topic": b.topic,
                "domain": b.domain,
                "confidence": b.confidence,
                "delta_confidence": b.delta_confidence,
                "filing_id": b.filing_id,
                "observed_at": b.observed_at.isoformat() if b.observed_at else None,
            }
            for b in self.session.exec(stmt).all()
        ]

    # -- Internal converters --------------------------------------------------

    def _to_record(self, pg_mem: PgMemory) -> MemoryRecord:
        return MemoryRecord(
            id=pg_mem.id,
            memory_type=MemoryType(pg_mem.memory_type),
            namespace=pg_mem.namespace,
            key=pg_mem.key,
            content=pg_mem.content or {},
            embedding_text=pg_mem.embedding_text or "",
            created_at=pg_mem.created_at.isoformat() if pg_mem.created_at else "",
            updated_at=pg_mem.updated_at.isoformat() if pg_mem.updated_at else "",
            access_count=pg_mem.access_count or 0,
            relevance_score=pg_mem.relevance_score or 1.0,
        )
