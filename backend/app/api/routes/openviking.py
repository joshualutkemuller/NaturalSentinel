"""OpenViking proxy routes.

Exposes the OpenViking context database over FastAPI so web clients can
reach the same context store that the MCP tools use.  All requests are
forwarded to the OpenViking server (configured via ``OPENVIKING_URL``).

Endpoints:
    POST /openviking/search          — semantic search
    GET  /openviking/list            — directory listing
    GET  /openviking/read            — read resource content
    POST /openviking/add             — ingest a URL or file
    POST /openviking/grep            — regex search
    POST /openviking/glob            — path-pattern match
    POST /openviking/session/commit  — commit session to long-term memory
    GET  /openviking/health          — OpenViking server health
"""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.naturalsentinel.mcp.openviking import server_url

logger = logging.getLogger("NaturalSentinel.OpenViking")

router = APIRouter()

_TIMEOUT = 30.0


def _ov_url(path: str) -> str:
    return f"{server_url().rstrip('/')}{path}"


def _forward_error(exc: httpx.HTTPStatusError) -> None:
    raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str
    target_uri: str = ""
    limit: int = 10


class ListRequest(BaseModel):
    uri: str = "viking://"


class ReadRequest(BaseModel):
    uri: str


class AddResourceRequest(BaseModel):
    path: str
    wait: bool = True


class GrepRequest(BaseModel):
    uri: str
    pattern: str
    case_insensitive: bool = False


class GlobRequest(BaseModel):
    pattern: str
    uri: str = "viking://"


class CommitSessionRequest(BaseModel):
    session_id: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/health")
async def openviking_health() -> dict[str, Any]:
    """Check whether the OpenViking server is reachable."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(_ov_url("/health"))
            resp.raise_for_status()
            return {"status": "ok", "url": server_url(), "detail": resp.json()}
        except Exception as exc:
            return {"status": "unavailable", "url": server_url(), "detail": str(exc)}


@router.post("/search")
async def openviking_search(body: SearchRequest) -> Any:
    """Semantic search across the OpenViking context store."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(
                _ov_url("/api/v1/search/find"),
                json={
                    "query": body.query,
                    "target_uri": body.target_uri,
                    "limit": body.limit,
                },
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            _forward_error(exc)


@router.post("/list")
async def openviking_list(body: ListRequest) -> Any:
    """List resources under a viking:// URI."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.get(
                _ov_url("/api/v1/fs/ls"), params={"uri": body.uri}
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            _forward_error(exc)


@router.post("/read")
async def openviking_read(body: ReadRequest) -> Any:
    """Read the full content of a resource at a viking:// URI."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.get(
                _ov_url("/api/v1/fs/read"), params={"uri": body.uri}
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            _forward_error(exc)


@router.post("/add")
async def openviking_add(body: AddResourceRequest) -> Any:
    """Ingest a URL or local file path into the OpenViking context store."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(
                _ov_url("/api/v1/resources"),
                json={"path": body.path, "wait": body.wait},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            _forward_error(exc)


@router.post("/grep")
async def openviking_grep(body: GrepRequest) -> Any:
    """Regex content search within resources under a viking:// URI."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(
                _ov_url("/api/v1/search/grep"),
                json={
                    "uri": body.uri,
                    "pattern": body.pattern,
                    "case_insensitive": body.case_insensitive,
                },
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            _forward_error(exc)


@router.post("/glob")
async def openviking_glob(body: GlobRequest) -> Any:
    """Path-pattern match (glob) within the OpenViking filesystem."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(
                _ov_url("/api/v1/search/glob"),
                json={"pattern": body.pattern, "uri": body.uri},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            _forward_error(exc)


@router.post("/session/commit")
async def openviking_commit_session(body: CommitSessionRequest) -> Any:
    """Commit a session to long-term memory in OpenViking."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(
                _ov_url(f"/api/v1/sessions/{body.session_id}/commit")
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            _forward_error(exc)
