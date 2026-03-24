"""Filing scan and analysis endpoints."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from naturalsentinel.cli import build_provider, create_runtime
from naturalsentinel.memory.store import MemoryStore
from naturalsentinel.models import RegulatoryDomain

logger = logging.getLogger(__name__)


router = APIRouter(tags=["filings"])

# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ScanRequest(BaseModel):
    domains: list[str] = Field(default_factory=list, description="Regulatory domains to scan")
    lookback_days: int = Field(default=7, ge=1, le=90)


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Filing text to analyze")
    domain: str = Field(default="sec", description="Regulatory domain")
    title: str = Field(default="Ad-hoc analysis", description="Filing title")


# ---------------------------------------------------------------------------
# Shared runtime helpers
# ---------------------------------------------------------------------------

_runtime = None


def _get_runtime():
    global _runtime
    if _runtime is None:
        provider_name = os.getenv("SENTINEL_PROVIDER", "mock")
        model = os.getenv("SENTINEL_MODEL")
        provider = build_provider(provider_name, model)
        db_path = os.getenv("SENTINEL_MEMORY_DB", "naturalsentinel_memory.db")
        memory = MemoryStore(db_path)
        _runtime = create_runtime(provider, memory=memory)
    return _runtime


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/scans", summary="Run a regulatory filing scan")
async def scan_filings(req: ScanRequest) -> dict[str, Any]:
    """Initiate a regulatory scan across specified domains."""
    runtime = _get_runtime()

    domains = req.domains or [d.value for d in RegulatoryDomain]
    try:
        results = runtime.execute_skill(
            "scan_cycle",
            {
                "domains": domains,
                "lookback_days": req.lookback_days,
            },
        )
        return {"status": "completed", "results": results.data or []}
    except Exception as exc:
        logger.exception("Scan failed")
        raise HTTPException(status_code=500, detail="Regulatory scan failed") from exc


@router.post("/filings/analyze", summary="Analyze filing text")
async def analyze_filing(req: AnalyzeRequest) -> dict[str, Any]:
    """Analyze a piece of regulatory text on demand."""
    runtime = _get_runtime()

    try:
        results = runtime.execute_skill(
            "analyze",
            {
                "text": req.text,
                "domain": req.domain,
                "title": req.title,
            },
        )
        return {"status": "completed", "result": results.data or {}}
    except Exception as exc:
        logger.exception("Filing analysis failed")
        raise HTTPException(status_code=500, detail="Filing analysis failed") from exc


@router.get("/domains", summary="List available regulatory domains")
async def list_domains() -> dict[str, Any]:
    """Return all supported regulatory domains."""
    return {"domains": [{"name": d.name, "value": d.value} for d in RegulatoryDomain]}
