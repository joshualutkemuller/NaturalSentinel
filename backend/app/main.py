from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Fail fast if sector/domain/state mappings are inconsistent with the
    # source enums. A typo in any mapping silently filters content out of
    # scans; we'd rather crash boot than ship broken filtering.
    from app.naturalsentinel.fetchers.config_validators import validate_mappings

    validate_mappings()

    # Initialize MCP server in-process on startup
    try:
        from app.naturalsentinel.mcp.server import create_mcp_app

        app.state.mcp_app = create_mcp_app()
    except Exception:
        app.state.mcp_app = None

    # Register built-in document review process definitions
    try:
        from sqlmodel import Session

        from app.core.db import engine
        from app.naturalsentinel.data.processes import (
            load_builtin_processes,
        )
        from app.naturalsentinel.mcp.openviking import _get_ov_client

        with Session(engine) as session:
            load_builtin_processes(
                ov_client=_get_ov_client(),
                session_db=session,
                skip_existing=True,
            )
    except Exception:
        pass  # Non-fatal — builtins can be registered manually via /documents/processes/

    yield
    # Cleanup on shutdown (connections closed by dependency injection)


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)
