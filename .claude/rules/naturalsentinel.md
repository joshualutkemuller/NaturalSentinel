---
globs: backend/app/naturalsentinel/**/*.py
---

# NaturalSentinel Domain Rules

## Skills
- Every capability is a `Skill` subclass from `agent_framework.py`
- `Permission` flags must be the narrowest set actually used — no speculative permissions
- `execute()` must always return a `SkillResult` — never raise exceptions out of it
- Register in `ALL_SKILLS` in `backend/app/naturalsentinel/skills/__init__.py`
- Latency classes: `instant` (<100ms), `fast` (<2s), `moderate` (2–15s), `slow` (15–60s), `batch` (>60s)

## Models
- `RegulatoryDomain`, `ChangeType`, `Severity` enums live in `backend/app/naturalsentinel/models.py`
- Domain value objects (never persisted): pure Pydantic in `naturalsentinel/models.py`
- Memory/infra tables: SQLModel with `table=True` in `naturalsentinel/memory/pg_models.py`

## Fetchers
- New fetchers go in `backend/app/naturalsentinel/fetchers/live/<agency>.py`
- Required return keys: `id`, `title`, `domain`, `source_url`, `published_date`, `change_type`, `raw_text`
- Use `HTTPClient` from `fetchers/live/http_client.py` for rate-limited requests
- Register in `_fetch_live()` in `fetchers/base.py` with try/except + `logger.warning` fallback
- Add new domains to `RegulatoryDomain` enum and `DOMAIN_BUSINESS_LINES`

## Providers
- LLM provider is pluggable: `anthropic`, `openai`, `gemini`, `ollama`, `mock`
- In dev/tests always use `mock` — no API credits, deterministic
- `SENTINEL_PROVIDER` + `SENTINEL_MODEL` in `.env` control the API backend

## Memory
- Memory types: `EPISODIC`, `ENTITY`, `PRECEDENT`, `BELIEF` (defined in `memory/types.py`)
- `PgMemoryStore` in `memory/pg_store.py` is the production backend
- Qdrant is used for semantic similarity search — must be running for `MEMORY_READ` skills
