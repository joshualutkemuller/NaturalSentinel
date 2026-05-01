from fastapi import APIRouter

from app.api.routes import (
    documents,
    filings,
    items,
    login,
    mcp,
    memory,
    openviking,
    private,
    sector_watch,
    tools,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(filings.router, prefix="/filings", tags=["filings"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
api_router.include_router(openviking.router, prefix="/openviking", tags=["openviking"])
api_router.include_router(
    sector_watch.router, prefix="/sector-watch", tags=["sector-watch"]
)
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
