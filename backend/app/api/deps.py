from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from qdrant_client import QdrantClient
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import TokenPayload, User
from app.naturalsentinel.agent_framework import AgentRuntime
from app.naturalsentinel.memory.pg_store import PgMemoryStore

# ---------------------------------------------------------------------------
# Qdrant singleton
# ---------------------------------------------------------------------------

_qdrant_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """Return the shared Qdrant client (lazy-initialized singleton)."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )
    return _qdrant_client


QdrantDep = Annotated[QdrantClient, Depends(get_qdrant_client)]

# ---------------------------------------------------------------------------
# OpenViking singleton (formalizes the module-level client in mcp/openviking.py)
# ---------------------------------------------------------------------------


def get_openviking_client():  # type: ignore[return]
    """Return the shared OpenViking SyncHTTPClient (lazy-initialized singleton)."""
    from app.naturalsentinel.mcp.openviking import _get_ov_client

    return _get_ov_client()


OpenVikingDep = Annotated[object, Depends(get_openviking_client)]

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


# NaturalSentinel dependencies


def get_ns_memory(session: SessionDep) -> PgMemoryStore:
    return PgMemoryStore(session)


NsMemoryDep = Annotated[PgMemoryStore, Depends(get_ns_memory)]


def get_ns_runtime(
    memory: NsMemoryDep,
) -> AgentRuntime:
    from app.naturalsentinel.providers import get_provider

    provider = get_provider(settings.SENTINEL_PROVIDER, settings.SENTINEL_MODEL)
    return AgentRuntime(provider=provider, memory=memory)


NsRuntimeDep = Annotated[AgentRuntime, Depends(get_ns_runtime)]
