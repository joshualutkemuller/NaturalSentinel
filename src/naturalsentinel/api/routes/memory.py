"""Memory search and feedback endpoints."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from naturalsentinel.memory.store import MemoryStore
from naturalsentinel.memory.types import MemoryType

logger = logging.getLogger(__name__)

router = APIRouter(tags=["memory"])

# ---------------------------------------------------------------------------
# Shared memory singleton
# ---------------------------------------------------------------------------

_memory: MemoryStore | None = None


def _get_memory() -> MemoryStore:
    global _memory
    if _memory is None:
        db_path = os.getenv("SENTINEL_MEMORY_DB", "naturalsentinel_memory.db")
        _memory = MemoryStore(db_path)
    return _memory


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class MemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    memory_type: str | None = Field(default=None, description="episodic, entity, or precedent")
    namespace: str | None = None


class FeedbackRequest(BaseModel):
    filing_id: str
    field: str
    old_value: str | None = None
    new_value: str
    reason: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/memory/search", summary="Semantic search across memory")
async def search_memory(req: MemorySearchRequest) -> dict[str, Any]:
    """Search the memory store with semantic similarity."""
    memory = _get_memory()

    # Convert string to MemoryType enum if provided
    memory_type_enum: MemoryType | None = None
    if req.memory_type:
        try:
            memory_type_enum = MemoryType(req.memory_type)
        except ValueError:
            valid = ", ".join(t.value for t in MemoryType)
            raise HTTPException(
                status_code=400,
                detail=f"Invalid memory_type '{req.memory_type}'. Must be one of: {valid}",
            )

    try:
        results = memory.recall(
            query=req.query,
            top_k=req.top_k,
            memory_type=memory_type_enum,
            namespace=req.namespace,
        )
        return {
            "query": req.query,
            "count": len(results),
            "results": [
                {
                    "id": r.id,
                    "memory_type": r.memory_type.value,
                    "namespace": r.namespace,
                    "key": r.key,
                    "content": r.content,
                    "relevance_score": r.relevance_score,
                }
                for r in results
            ],
        }
    except Exception as exc:
        logger.exception("Memory search failed")
        raise HTTPException(status_code=500, detail="Memory search failed") from exc


@router.get("/memory/stats", summary="Memory system statistics")
async def memory_stats() -> dict[str, Any]:
    """Return statistics about the memory store."""
    memory = _get_memory()
    return memory.stats()


@router.post("/feedback", summary="Record human correction")
async def record_feedback(req: FeedbackRequest) -> dict[str, str]:
    """Record a human correction for a filing analysis."""
    memory = _get_memory()
    try:
        memory.record_feedback(
            filing_id=req.filing_id,
            field=req.field,
            old_value=req.old_value or "",
            new_value=req.new_value,
            reason=req.reason or "",
        )
        return {"status": "recorded", "filing_id": req.filing_id, "field": req.field}
    except Exception as exc:
        logger.exception("Failed to record feedback for filing %s", req.filing_id)
        raise HTTPException(status_code=500, detail="Failed to record feedback") from exc


@router.get(
    "/entities/{entity_name}/relations",
    summary="Get entity relations from knowledge graph",
)
async def entity_relations(entity_name: str) -> dict[str, Any]:
    """Query the knowledge graph for an entity's relationships."""
    memory = _get_memory()
    try:
        relations = memory.get_related_entities(entity_name)
        return {"entity": entity_name, "relations": relations}
    except Exception as exc:
        logger.exception("Failed to get relations for entity %s", entity_name)
        raise HTTPException(status_code=500, detail="Failed to get entity relations") from exc
