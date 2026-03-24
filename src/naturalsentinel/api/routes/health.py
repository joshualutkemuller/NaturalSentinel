"""Health and readiness endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict:
    """Readiness probe — checks database connectivity when DATABASE_URL is set."""
    checks: dict[str, str] = {}
    database_url = os.getenv("DATABASE_URL", "")

    if database_url:
        try:
            import psycopg

            conn = await psycopg.AsyncConnection.connect(database_url, connect_timeout=5)
            await conn.execute("SELECT 1")
            await conn.close()
            checks["database"] = "ok"
        except ImportError:
            checks["database"] = "skipped (psycopg not installed)"
        except Exception as exc:
            checks["database"] = f"error: {exc}"
            return {"status": "degraded", "checks": checks}

    return {"status": "ok", "checks": checks}
