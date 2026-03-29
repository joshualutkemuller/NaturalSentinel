---
description: Run the test suite, type checker, and linter. Accepts scope: backend, frontend, types, lint, or empty for everything.
allowed-tools: Bash
---

Run NaturalSentinel tests and static analysis.

Scope: $ARGUMENTS
(one of: `backend`, `frontend`, `types`, `lint`, or empty for everything)

## Backend tests

```bash
cd backend && uv run pytest -x --tb=short
```

Flags:
- `-m "not slow"` — skip tests that hit live external APIs (marked `@pytest.mark.slow`)
- `--cov=app --cov-report=term-missing` — coverage report
- `-k "<pattern>"` — filter by test name
- `tests/api/routes/test_<name>.py` — single file

Slow tests require live network + API keys — run explicitly:
```bash
uv run pytest -m slow -x --tb=short
```

## Backend type checking

```bash
cd backend && uv run mypy app/
```

## Backend linting

```bash
cd backend && uv run ruff check app/ && uv run ruff format --check app/
```

Auto-fix:
```bash
uv run ruff check --fix app/ && uv run ruff format app/
```

## Frontend type checking

```bash
cd frontend && bunx tsc --noEmit
```

## Frontend linting

```bash
cd frontend && bun run lint
```

Biome auto-fix:
```bash
cd frontend && bunx biome check --write src/
```

## Frontend E2E (Playwright)

Requires all services running (`/dev-services`):
```bash
cd frontend && bun run test
```

Interactive:
```bash
bun run test:ui
```

Single spec:
```bash
bun run test tests/items.spec.ts
```

## Output

Report pass/fail counts, failing test names with file:line, type errors with context, and lint errors with suggested fixes.
