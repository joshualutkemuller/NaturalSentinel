---
description: Add a new SQLModel table, Pydantic schemas, CRUD helpers, and trigger a migration. Use when introducing a new database-backed entity.
context: fork
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Add a new SQLModel table, schemas, and CRUD helpers.

Model name (PascalCase): $ARGUMENTS

## Step 1 — Choose location

| Model type | File |
|-----------|------|
| Core app concept (user-scoped, auth-adjacent) | `backend/app/models.py` |
| NS domain infrastructure (audit, governance, memory) | `backend/app/naturalsentinel/memory/pg_models.py` |
| Domain value object, never persisted | `backend/app/naturalsentinel/models.py` (pure Pydantic only) |

Read the target file first to understand the existing patterns before adding.

## Step 2 — Define the model

Follow the layered pattern from `backend/app/models.py` (read it first):

```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel
from app.models import get_datetime_utc  # reuse, do not redefine

class <Name>Base(SQLModel):
    field_one: str = Field(min_length=1, max_length=255)

class <Name>Create(<Name>Base):
    pass

class <Name>Update(SQLModel):
    field_one: str | None = Field(default=None, min_length=1, max_length=255)

class <Name>(<Name>Base, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    owner_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")

class <Name>Public(<Name>Base):
    id: uuid.UUID
    created_at: datetime
```

**Hard rules:**
- UUID PKs — `default_factory=uuid.uuid4`
- `DateTime(timezone=True)` always — never naive datetimes
- `get_datetime_utc` for default factory — not `datetime.utcnow` (deprecated) or bare `datetime.now`
- FK fields use `ondelete="CASCADE"` unless intentional soft-delete

## Step 3 — Add CRUD functions

In `backend/app/crud.py`, following the `create_item` / `session.exec(select(...))` pattern:

```python
def create_<name>(*, session: Session, owner_id: uuid.UUID, obj_in: <Name>Create) -> <Name>:
    db_obj = <Name>.model_validate(obj_in, update={"owner_id": owner_id})
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj

def get_<name>(*, session: Session, id: uuid.UUID) -> <Name> | None:
    return session.get(<Name>, id)
```

Always pass `session` as keyword argument.

## Step 4 — Run migration

Run `/db-migrate "add <snake_name> table"` (or invoke the db-migrate skill directly).

## Step 5 — Type-check

```bash
cd backend && uv run mypy app/models.py app/crud.py
```
