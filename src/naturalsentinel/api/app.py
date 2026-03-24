"""NaturalSentinel FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI

from naturalsentinel.api.routes import filings, health, memory

app = FastAPI(
    title="NaturalSentinel",
    description="Agentic regulatory change monitor with persistent memory",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(health.router)
app.include_router(filings.router, prefix="/api/v1")
app.include_router(memory.router, prefix="/api/v1")
