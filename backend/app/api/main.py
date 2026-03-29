from fastapi import APIRouter

from app.api.routes import (
    filings,
    items,
    login,
    mcp,
    memory,
    private,
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


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
