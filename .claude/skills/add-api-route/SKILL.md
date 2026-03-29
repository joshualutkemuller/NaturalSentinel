---
description: Scaffold a new FastAPI router module following NaturalSentinel conventions. Handles route file, main.py registration, client regeneration, and a basic test.
context: fork
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Scaffold a new FastAPI router. Route name and prefix: $ARGUMENTS
(e.g., `alerts /alerts`)

## Step 1 — Read the reference

Read `backend/app/api/routes/filings.py` to load the exact pattern before writing anything.

## Step 2 — Create the route file

Create `backend/app/api/routes/<name>.py`:

```python
"""<Description> API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep  # add NsMemoryDep/NsRuntimeDep if needed

router = APIRouter()


class <Name>Request(BaseModel):
    ...


@router.get("/")
def list_<name>(
    _current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, Any]:
    ...
```

**Dependency rules:**
- `SessionDep` not bare `Session`
- `CurrentUser` not manual JWT decode
- `NsMemoryDep` — direct memory store access without full runtime
- `NsRuntimeDep` — only when delegating to `AgentRuntime.execute_skill()`
- Do NOT mix `NsRuntimeDep` with direct `SessionDep` DB writes in the same endpoint

**Response types:** prefer a named Pydantic/SQLModel schema with `response_model=` on the decorator over raw `dict[str, Any]` for public endpoints.

## Step 3 — Register in api/main.py

Read `backend/app/api/main.py`. Add import and `include_router` call following the alphabetical import ordering:
```python
from app.api.routes import <name>
...
api_router.include_router(<name>.router, prefix="/<prefix>", tags=["<tag>"])
```

## Step 4 — Regenerate client

```bash
bash scripts/generate-client.sh
```

## Step 5 — Write a test

Create `backend/tests/api/routes/test_<name>.py` mirroring `tests/api/routes/test_items.py`:
- Use `client` and `superuser_token_headers` fixtures from `conftest.py`
- Test minimum: unauthenticated 401, happy path response shape
