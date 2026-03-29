---
description: Generate an Alembic migration for model changes and apply it. Use after adding or modifying any SQLModel table=True class.
allowed-tools: Bash, Read, Edit, Glob
---

Generate and apply an Alembic migration.

Migration message: $ARGUMENTS

## Rules

- All alembic commands run from `backend/` using `uv run alembic` — never bare `alembic`
- Config: `backend/alembic.ini` — versions: `backend/app/alembic/versions/`
- New `table=True` models must be imported in `backend/app/alembic/env.py`
  - `app.models` is imported via `from app.models import SQLModel`
  - `app.naturalsentinel.memory.pg_models` is already imported — NS memory tables auto-detected
  - Any other new table file must be added to `env.py` explicitly

## Steps

1. Read `backend/app/alembic/env.py` lines 1–30 and verify the new model's module is imported. Add the import if missing.

2. Generate:
   ```
   cd backend && uv run alembic revision --autogenerate -m "$ARGUMENTS"
   ```

3. Read the generated file in `backend/app/alembic/versions/`. Review for autogenerate gaps:
   - `DateTime(timezone=True)` — must be explicit
   - `sa.JSON` vs `sa.Text` for dict/list columns
   - `UniqueConstraint` and named indexes
   - `server_default=sa.text("...")`
   - `cascade` on foreign keys
   Fix any issues before applying.

4. Apply: `cd backend && uv run alembic upgrade head`

5. Verify: `uv run alembic current`

To roll back: `uv run alembic downgrade -1`
