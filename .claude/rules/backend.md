---
globs: backend/**/*.py
---

# Backend Python Rules

## Commands
- Always use `uv run` — never bare `python`, `pytest`, or `alembic`
- Alembic commands run from `backend/` with `uv run alembic ...`

## Dependencies (FastAPI)
- Use `SessionDep` (not bare `Session`) for DB access
- Use `CurrentUser` (not manual JWT decode) for auth
- Use `NsMemoryDep` for direct memory store access
- Use `NsRuntimeDep` only when delegating to `AgentRuntime.execute_skill()`
- All deps defined in `backend/app/api/deps.py` — never construct them inline

## Models
- UUID primary keys: `Field(default_factory=uuid.uuid4, primary_key=True)`
- Timezone-aware datetimes: `sa_type=DateTime(timezone=True)` with `get_datetime_utc` factory
- Never use `datetime.utcnow()` (deprecated) or naive `datetime.now()`
- Schema layers: `<Name>Base` → `<Name>Create` → `<Name>Update` → `<Name>` (table) → `<Name>Public`
- New `table=True` models must be imported in `backend/app/alembic/env.py`

## CRUD
- Pass `session` as keyword argument: `create_foo(*, session: Session, ...)`
- Always `session.commit()` then `session.refresh(db_obj)` before returning

## Skills
- `Permission` flags: declare the narrowest set actually used
- `execute()` never raises — always returns `SkillResult`
- Register new skills in `ALL_SKILLS` in `backend/app/naturalsentinel/skills/__init__.py`

## Routes
- New router files require registration in `backend/app/api/main.py`
- Use `response_model=` on the decorator for typed public responses

## Testing
- Run with `uv run pytest -m "not slow"` to skip live API tests
- Test fixtures are in `backend/tests/conftest.py`
