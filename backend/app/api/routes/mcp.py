"""MCP server transport endpoints.

Exposes the NaturalSentinel MCP server (initialized in app lifespan) over:
- SSE transport:              GET  /mcp/sse
- Streamable-HTTP transport:  POST /mcp/message
- Health check:               GET  /mcp/health
"""

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter()


@router.get("/health")
def mcp_health(request: Request) -> dict[str, Any]:
    """Report MCP server status."""
    mcp_app = getattr(request.app.state, "mcp_app", None)
    return {
        "status": "ok" if mcp_app is not None else "unavailable",
        "transport_modes": ["sse", "streamable-http", "stdio"],
    }


@router.post("/message")
async def mcp_message(request: Request) -> JSONResponse:
    """Streamable-HTTP transport: handle a single MCP JSON-RPC request.

    MCP clients send JSON-RPC 2.0 requests here and receive responses.
    The StandaloneServer processes them synchronously; async transport
    via the MCP SDK can be wired here once the SSE session management
    layer is added.
    """
    mcp_app = getattr(request.app.state, "mcp_app", None)
    if mcp_app is None:
        return JSONResponse({"error": "MCP server not initialized"}, status_code=503)
    body = await request.json()
    response = mcp_app.handle_request(body)
    return JSONResponse(response)


@router.get("/sse")
async def mcp_sse(request: Request):
    """SSE transport: stream MCP events to connected clients.

    This is a minimal SSE implementation. For production, wire the MCP SDK's
    SseServerTransport to the same StandaloneServer/Server instance stored in
    app.state.mcp_app.
    """
    mcp_app = getattr(request.app.state, "mcp_app", None)

    async def event_stream():
        # Send initial tools list as an SSE event
        if mcp_app is not None:
            tools_response = mcp_app.handle_request({"method": "tools/list"})
            yield f"event: tools\ndata: {json.dumps(tools_response)}\n\n"
        else:
            yield 'event: error\ndata: {"error": "MCP server not initialized"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
