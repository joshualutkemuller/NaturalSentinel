"""Skill registry and execution API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUser, NsRuntimeDep

router = APIRouter()


@router.get("/")
def list_tools(
    _current_user: CurrentUser,
    runtime: NsRuntimeDep,
) -> dict[str, Any]:
    """List all registered skills with their metadata."""
    return {"tools": runtime.registry.catalog()}


@router.get("/{tool_name}")
def describe_tool(
    tool_name: str,
    _current_user: CurrentUser,
    runtime: NsRuntimeDep,
) -> dict[str, Any]:
    """Describe a single skill's inputs, outputs, and permissions."""
    skill = runtime.registry.get(tool_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    meta = skill.metadata
    return {
        "name": meta.name,
        "description": meta.description,
        "version": meta.version,
        "permissions": str(meta.permissions),
        "latency": meta.latency.value,
        "parameters": [
            {
                "name": p.name,
                "type": p.type,
                "required": p.required,
                "description": p.description,
                "default": p.default,
            }
            for p in meta.parameters
        ],
        "returns": meta.returns,
        "dependencies": meta.dependencies,
        "tags": meta.tags,
    }


class RunToolRequest(BaseModel):
    params: dict[str, Any] = {}


@router.post("/{tool_name}/run")
def run_tool(
    tool_name: str,
    request: RunToolRequest,
    current_user: CurrentUser,
    runtime: NsRuntimeDep,
) -> dict[str, Any]:
    """Execute a named skill (superuser only)."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    skill = runtime.registry.get(tool_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    result = runtime.execute_skill(tool_name, request.params)
    return {
        "tool": tool_name,
        "success": result.success,
        "data": result.data,
        "error": result.error,
        "duration_ms": result.duration_ms,
        "token_usage": result.token_usage,
    }
