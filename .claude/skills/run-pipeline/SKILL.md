---
description: Trigger a NaturalSentinel regulatory scan cycle or analyze a specific filing via CLI or API.
allowed-tools: Bash
---

Trigger a NaturalSentinel scan or analyze a filing.

Mode and options: $ARGUMENTS
(e.g., `cli --domains sec cfpb --days 7`, `api`, `file path/to/doc.txt --domain sec`)

## CLI mode

```bash
cd backend && uv run python -m app.naturalsentinel.cli \
  --provider mock \
  --domains sec cfpb \
  --days 30
```

**Providers:** `anthropic`, `openai`, `gemini`, `ollama`, `mock`
- `mock` — dev/testing, no API key, deterministic output
- `anthropic` → `ANTHROPIC_API_KEY`; `openai` → `OPENAI_API_KEY`; `gemini` → `GOOGLE_API_KEY`

**Domains:** `sec`, `cfpb`, `fed`, `fda`, `epa`, `ustr`, `fhfa`, `occ`, `finra`, `cftc`, `fdic`, `basel`
Omit `--domains` to scan all.

**Reset dedup state** (force re-analysis of all filings):
```bash
uv run python -m app.naturalsentinel.cli --provider mock --reset
```

## API mode

Get a JWT:
```bash
curl -s -X POST http://localhost:8000/api/v1/login/access-token \
  -d "username=<email>&password=<password>" \
  -H "Content-Type: application/x-www-form-urlencoded" | jq .access_token
```

Trigger scan:
```bash
curl -s -X POST http://localhost:8000/api/v1/filings/scan \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"domains": ["sec", "cfpb"], "since_days": 30}'
```

Analyze single filing:
```bash
curl -s -X POST http://localhost:8000/api/v1/filings/analyze \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"filing_id": "...", "title": "...", "summary": "...", "domain": "sec", "text": "..."}'
```

The API backend's LLM is controlled by `SENTINEL_PROVIDER` + `SENTINEL_MODEL` in `.env`.

## File mode

```bash
cd backend && uv run python -m app.naturalsentinel.cli \
  --input-path path/to/document.txt \
  --input-domain sec \
  --provider anthropic
```

## Notes

- `mock` provider is always safe — no API credits consumed
- Memory DB errors: check `SENTINEL_MEMORY_DB` in `.env` points to running Postgres or valid SQLite path
- Qdrant must be running for `MEMORY_READ` skills — use `/dev-services` to start it
