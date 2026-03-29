"""Regulatory filings API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUser, NsMemoryDep, NsRuntimeDep
from app.naturalsentinel.memory.types import MemoryType

router = APIRouter()


class AnalyzeRequest(BaseModel):
    filing_id: str
    title: str
    summary: str
    domain: str
    text: str | None = None


class ScanRequest(BaseModel):
    domains: list[str] | None = None
    since_days: int = 30


@router.post("/analyze")
def analyze_filing(
    request: AnalyzeRequest,
    _current_user: CurrentUser,
    runtime: NsRuntimeDep,
) -> dict[str, Any]:
    """Analyze a regulatory filing and return impact assessment."""
    params = {
        "filing_id": request.filing_id,
        "title": request.title,
        "summary": request.summary,
        "domain": request.domain,
        "text": request.text or "",
    }
    result = runtime.execute_skill("analyze", params)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return {"filing_id": request.filing_id, "result": result.data}


@router.post("/scan")
def scan_filings(
    request: ScanRequest,
    _current_user: CurrentUser,
    runtime: NsRuntimeDep,
) -> dict[str, Any]:
    """Trigger a full domain scan cycle."""
    params: dict[str, Any] = {"since_days": request.since_days}
    if request.domains:
        params["domains"] = request.domains
    result = runtime.execute_skill("scan_cycle", params)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return {"result": result.data, "duration_ms": result.duration_ms}


@router.get("/")
def list_filings(
    _current_user: CurrentUser,
    memory: NsMemoryDep,
    limit: int = 20,
) -> dict[str, Any]:
    """List recent episodic filings stored in memory."""
    records = memory.list_by_type(MemoryType.EPISODIC, limit=limit)
    return {
        "total": len(records),
        "filings": [
            {
                "id": r.key,
                "namespace": r.namespace,
                "updated_at": r.updated_at,
                "summary": r.content.get("filing", {}).get("summary", ""),
            }
            for r in records
        ],
    }


@router.get("/{filing_id}")
def get_filing(
    filing_id: str,
    _current_user: CurrentUser,
    memory: NsMemoryDep,
) -> dict[str, Any]:
    """Retrieve a stored filing by ID."""
    record = memory.get(f"episodic:{filing_id}")
    if not record:
        raise HTTPException(status_code=404, detail="Filing not found")
    return {
        "id": record.key,
        "namespace": record.namespace,
        "content": record.content,
        "updated_at": record.updated_at,
        "access_count": record.access_count,
    }
