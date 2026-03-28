# NaturalSentinel - Development

## Quick Start

1. Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

2. Start the stack:

```bash
docker compose watch
```

3. Open your browser:

| Service | URL |
|---------|-----|
| Frontend | <http://localhost:5173> |
| Backend (API) | <http://localhost:8000> |
| Swagger UI (interactive docs) | <http://localhost:8000/docs> |
| ReDoc (alternative docs) | <http://localhost:8000/redoc> |
| Qdrant (vector DB dashboard) | <http://localhost:6333/dashboard> |
| MailCatcher | <http://localhost:1080> |

Postgres is exposed on **port 5433** (to avoid conflicts with a local Postgres on 5432). Connect with any DB client using the credentials in `.env`.

**Note**: The first time you start the stack it may take a minute. The backend waits for the database to be healthy and runs migrations before starting. Check progress with:

```bash
docker compose logs -f backend
```

## Environment Variables

All configuration lives in `.env` at the project root. See `.env.example` for a documented reference of every variable.

### NaturalSentinel-specific variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SENTINEL_PROVIDER` | `mock` | LLM provider: `anthropic`, `openai`, `gemini`, `ollama`, or `mock` |
| `SENTINEL_MODEL` | _(none)_ | Model name (provider-specific, e.g. `claude-sonnet-4-20250514`) |
| `SENTINEL_STATE` | `monitor_state.json` | Agent state file path |
| `SENTINEL_MEMORY_DB` | `naturalsentinel_memory.db` | Memory store — SQLite file path or `postgresql://` URL |
| `ANTHROPIC_API_KEY` | _(none)_ | Required when `SENTINEL_PROVIDER=anthropic` |
| `OPENAI_API_KEY` | _(none)_ | Required when `SENTINEL_PROVIDER=openai` |
| `GOOGLE_API_KEY` | _(none)_ | Required when `SENTINEL_PROVIDER=gemini` |

After changing any variables, restart the stack:

```bash
docker compose watch
```

## Services

### Qdrant (Vector Database)

Qdrant provides vector similarity search for the NaturalSentinel memory and embeddings system. It runs alongside PostgreSQL — Postgres stores relational data (users, items, filings), while Qdrant stores document embeddings for semantic search.

- Dashboard: <http://localhost:6333/dashboard>
- API: <http://localhost:6333>
- Data is persisted in the `qdrant-data` Docker volume.

### MCP Server

The Model Context Protocol server starts in-process with the FastAPI backend (see `app/main.py` lifespan). MCP endpoints are available at `/api/v1/mcp/`.

### Mailcatcher

Mailcatcher intercepts all emails sent by the backend during local development. Instead of sending real emails, they are captured and displayed at <http://localhost:1080>.

The Docker Compose override automatically configures SMTP to point at Mailcatcher (port 1025, TLS off).

## Local Development (outside Docker)

The Docker Compose services use the same ports as local dev servers, so you can stop any Docker service and replace it with a local process.

### Frontend

The Docker frontend runs Vite's dev server with HMR inside the container. Source files (`src/`, `public/`, `index.html`) are volume-mounted so edits are reflected immediately without rebuilding.

If you prefer running Vite outside Docker (e.g. for faster HMR on macOS):

```bash
docker compose stop frontend
cd frontend
bun run dev
```

### Running the backend locally

```bash
docker compose stop backend
cd backend
fastapi dev app/main.py
```

When running outside Docker, the backend reads `../.env` automatically (configured in `app/core/config.py`). If your local Postgres is on a non-default port, set `POSTGRES_SERVER`, `POSTGRES_PORT`, etc. in `.env` accordingly.

### Running the NaturalSentinel CLI

The project includes a CLI for agent operations:

```bash
cd backend
uv run python -m app.naturalsentinel.cli
```

## Deployment

- **Backend**: Fly.io — deploy using `fly.toml` (see Fly.io docs for setup)
- **Frontend**: Vercel — deploys from the `frontend/` directory

Docker Compose is for **local development only**. Production infrastructure is managed by Fly.io and Vercel.

## API Routes

The backend exposes these route groups under `/api/v1/`:

| Prefix | Module | Description |
|--------|--------|-------------|
| `/login` | `login.py` | Authentication (JWT tokens) |
| `/users` | `users.py` | User management |
| `/utils` | `utils.py` | Health check, utilities |
| `/items` | `items.py` | CRUD items |
| `/filings` | `filings.py` | Regulatory filing documents |
| `/memory` | `memory.py` | Memory store access |
| `/tools` | `tools.py` | Tool registry |
| `/mcp` | `mcp.py` | Model Context Protocol endpoints |

## Docker Compose Files

| File | Purpose |
|------|---------|
| `compose.yml` | Core stack: db, prestart, backend, frontend, qdrant |
| `compose.override.yml` | Local dev overrides: dev target for frontend, mailcatcher, hot-reload, port mappings |

The override file is loaded automatically by `docker compose`. Environment variables come from `.env`.

## Pre-commits and Code Linting

We use [prek](https://prek.j178.dev/) for pre-commit hooks. Install it (from inside `backend/`):

```bash
uv run prek install -f
```

Run manually on all files:

```bash
uv run prek run --all-files
```

Hooks configured in `.pre-commit-config.yaml`:
- Large file check
- TOML/YAML validation
- Trailing whitespace / end-of-file fixes
- `ruff` (Python linting + formatting)
- `biome` (frontend linting)
