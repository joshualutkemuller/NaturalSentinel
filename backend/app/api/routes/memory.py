"""Memory recall and belief state API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUser, NsMemoryDep

router = APIRouter()


class RecallRequest(BaseModel):
    query: str
    top_k: int = 3


@router.post("/recall")
def recall_memory(
    request: RecallRequest,
    _current_user: CurrentUser,
    memory: NsMemoryDep,
) -> dict[str, Any]:
    """Semantic search across the memory store."""
    records = memory.recall(request.query, top_k=request.top_k)
    return {
        "query": request.query,
        "results": [
            {
                "id": r.id,
                "type": r.memory_type.value,
                "key": r.key,
                "namespace": r.namespace,
                "relevance_score": r.relevance_score,
                "content": r.content,
                "updated_at": r.updated_at,
            }
            for r in records
        ],
    }


@router.get("/stats")
def memory_stats(
    _current_user: CurrentUser,
    memory: NsMemoryDep,
) -> dict[str, Any]:
    """Return memory counts broken down by type and namespace."""
    return memory.stats()


@router.delete("/{memory_id}")
def delete_memory(
    memory_id: str,
    current_user: CurrentUser,
    memory: NsMemoryDep,
) -> dict[str, str]:
    """Remove a memory record by ID (superuser only)."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    from app.naturalsentinel.memory.pg_models import PgMemory

    pg_mem = memory.session.get(PgMemory, memory_id)
    if not pg_mem:
        raise HTTPException(status_code=404, detail="Memory record not found")
    memory.session.delete(pg_mem)
    memory.session.commit()
    return {"deleted": memory_id}


@router.get("/beliefs")
def list_beliefs(
    _current_user: CurrentUser,
    memory: NsMemoryDep,
    domain: str | None = None,
) -> dict[str, Any]:
    """List belief states, optionally filtered by domain."""
    return {"beliefs": memory.get_belief_states(domain=domain)}


@router.get("/beliefs/{topic}")
def get_belief_history(
    topic: str,
    _current_user: CurrentUser,
    memory: NsMemoryDep,
    domain: str = "global",
) -> dict[str, Any]:
    """Get confidence history for a specific topic/domain pair."""
    history = memory.get_belief_history(topic=topic, domain=domain)
    return {"topic": topic, "domain": domain, "history": history}
