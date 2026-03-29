# NaturalSentinel — Project Context

NaturalSentinel is an agentic regulatory change monitor. It watches regulatory filings from SEC, CFPB, Fed, FDA, EPA, USTR, FINRA, CFTC, and others, runs LLM-powered impact analysis, maintains a persistent memory system, and surfaces briefings via a FastAPI + React interface.

Built on the `full-stack-fastapi-template` (FastAPI, SQLModel, Alembic, React, TanStack Router, ShadcnUI).

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend runtime | Python 3.12+, FastAPI, UV |
| ORM / DB | SQLModel (Pydantic + SQLAlchemy), PostgreSQL, psycopg3 |
| Migrations | Alembic (`backend/alembic.ini`, versions in `backend/app/alembic/versions/`) |
| Auth | JWT (PyJWT), argon2/bcrypt via pwdlib |
| Agent / skills | `AgentRuntime` + `Skill` in `backend/app/naturalsentinel/agent_framework.py` |
| LLM providers | Anthropic, OpenAI, Gemini, Ollama, Mock — in `backend/app/naturalsentinel/providers/` |
| Memory | `PgMemoryStore` backed by PostgreSQL + Qdrant for semantic similarity |
| Fetchers | SEC EDGAR, BIS, Federal Register, FINRA — `backend/app/naturalsentinel/fetchers/live/` |
| Frontend | React 19, TanStack Router (file-based), TanStack Query, ShadcnUI, Tailwind CSS v4 |
| API client | Auto-generated from OpenAPI via `@hey-api/openapi-ts` → `frontend/src/client/` |
| Linting | ruff + mypy (backend), Biome (frontend) |
| Testing | pytest (backend), Playwright (frontend E2E) |
| Infra | Docker Compose: `db` (postgres), `backend`, `frontend`, `qdrant` |

---

## Key Conventions

### Backend

- **Always use `uv run`** for Python — never bare `python` or `alembic`
- **Alembic commands** run from `backend/` with `uv run alembic ...`
- **Dependencies** in route handlers: `SessionDep` (not bare `Session`), `CurrentUser` (not raw JWT decode), `NsMemoryDep` / `NsRuntimeDep` for NS operations — all defined in `backend/app/api/deps.py`
- **New `table=True` models** must be imported in `backend/app/alembic/env.py` for autogenerate to detect them
  - Platform/app tables: add to `backend/app/models.py`, then import in `env.py`
  - NS memory/infra tables: add to `backend/app/naturalsentinel/memory/pg_models.py` (already imported via `import app.naturalsentinel.memory.pg_models`)
  - Domain value objects never persisted: `backend/app/naturalsentinel/models.py` (pure Pydantic, no `table=True`)
- **Model naming pattern**: `<Name>Base` → `<Name>Create` → `<Name>Update` → `<Name>` (table) → `<Name>Public`
- **UUID PKs + timezone-aware datetimes**: always `Field(default_factory=uuid.uuid4)` and `sa_type=DateTime(timezone=True)` with `get_datetime_utc` factory
- **New routes** require two edits: the route file + registration in `backend/app/api/main.py`
- **CRUD functions** always pass `session` as keyword argument

### NaturalSentinel Agent

- Every capability is a `Skill` subclass with declared `Permission` flags — use the narrowest set that works
- Register new skills in `ALL_SKILLS` in `backend/app/naturalsentinel/skills/__init__.py`
- Use `mock` provider in dev — no API keys needed, deterministic output
- `SENTINEL_PROVIDER` + `SENTINEL_MODEL` in `.env` control the API backend's LLM; CLI uses `--provider` flag

### Frontend

- **Route files** live at `frontend/src/routes/_layout/<name>.tsx` — TanStack Router Vite plugin auto-generates the route tree on `bun run dev`; never edit `.tanstack/routeTree.gen.ts` manually
- **Data fetching**: `useSuspenseQuery` + `get<Name>QueryOptions()` function, always wrapped in `<Suspense>`
- **New pages** need a sidebar entry in `frontend/src/components/Sidebar/AppSidebar.tsx` (`baseItems` array)
- **Forms**: `react-hook-form` + `zod` + ShadcnUI `<Form>`, `<FormField>`, `<FormItem>`, `<FormControl>`
- **Notifications**: `useCustomToast` hook (wraps Sonner)
- **After route/model changes**: run `bash scripts/generate-client.sh` from repo root to regenerate `frontend/src/client/`

---

## Project Layout

```
NaturalSentinel/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py          # SessionDep, CurrentUser, NsMemoryDep, NsRuntimeDep
│   │   │   ├── main.py          # Router registration
│   │   │   └── routes/          # One file per domain
│   │   ├── alembic/             # Migrations (env.py + versions/)
│   │   ├── core/                # config.py, db.py, security.py
│   │   ├── models.py            # Platform SQLModel tables + schemas
│   │   ├── crud.py              # CRUD helpers
│   │   └── naturalsentinel/
│   │       ├── agent_framework.py   # AgentRuntime, Skill, Permission, SkillResult
│   │       ├── models.py            # Domain value objects (pure Pydantic)
│   │       ├── skills/              # Skill subclasses + ALL_SKILLS registry
│   │       ├── fetchers/live/       # Per-agency HTTP fetchers
│   │       ├── memory/              # PgMemoryStore, pg_models.py, similarity
│   │       ├── providers/           # LLM adapters (anthropic, openai, gemini, mock)
│   │       └── mcp/                 # MCP server
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── client/              # Auto-generated — do not edit
│   │   ├── routes/_layout/      # Page components (file-based routing)
│   │   ├── components/
│   │   │   ├── Sidebar/AppSidebar.tsx
│   │   │   ├── Common/DataTable.tsx
│   │   │   └── ui/              # ShadcnUI primitives
│   │   └── hooks/
│   └── package.json
├── scripts/
│   └── generate-client.sh       # Dump OpenAPI → regenerate TS client
├── compose.yml
├── .env                         # gitignored
└── .env.example
```

---

## Environment Variables (key ones)

| Variable | Purpose |
|----------|---------|
| `SENTINEL_PROVIDER` | LLM backend: `anthropic`, `openai`, `gemini`, `ollama`, `mock` |
| `SENTINEL_MODEL` | Model name (e.g., `claude-opus-4-6`) |
| `SENTINEL_MEMORY_DB` | Memory DB connection (Postgres DSN or SQLite path) |
| `POSTGRES_*` | Database credentials |
| `SECRET_KEY` | JWT signing key |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` | Provider keys |

---

## Running Locally

```bash
# Start all services
docker compose up -d

# Backend (from backend/)
uv run fastapi dev app/main.py

# Frontend
cd frontend && bun run dev

# Generate TS client after backend changes
bash scripts/generate-client.sh
```

Health endpoints: `http://localhost:8000/api/v1/utils/health-check/` · `http://localhost:5173` · `http://localhost:6333/healthz`
