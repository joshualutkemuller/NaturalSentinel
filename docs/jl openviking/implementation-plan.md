# OpenViking Implementation Plan

End-to-end plan for integrating OpenViking as a context database into NaturalSentinel.

---

## Current State: What Exists

| Component | File | Status |
|-----------|------|--------|
| Python bridge client | `backend/app/naturalsentinel/mcp/openviking.py` | Done -- wraps `SyncHTTPClient` with 7 operations |
| FastAPI proxy routes | `backend/app/api/routes/openviking.py` | Done -- 8 HTTP endpoints forwarding to OV server |
| MCP tool definitions | `backend/app/naturalsentinel/mcp/server.py` | Done -- 7 MCP tools registered |
| Route registration | `backend/app/api/main.py` | Done -- `/openviking` prefix |
| Config setting | `backend/app/core/config.py` | Done -- `OPENVIKING_URL` |
| PyPI dependency | `backend/pyproject.toml` | Done -- `openviking>=0.2` |
| Onboarding docs | `docs/openviking-onboarding.md` | Done |

All of this is a **thin proxy layer** -- it forwards HTTP calls to the OV server but doesn't integrate with the skill framework, memory system, or scan pipeline.

---

## What's Missing

| Gap | What's Needed | Why It Matters |
|-----|--------------|----------------|
| No OpenViking in Docker Compose | Add `openviking` service to `compose.yml` | Can't start locally without this |
| No Skill integration | No `Skill` subclass that uses OV for retrieval/storage | The 34 existing skills still use `PgMemoryStore` only |
| No dual-storage memory | `PgMemoryStore` doesn't write to or read from OV | Filings/impacts never flow into the `viking://` filesystem |
| No frontend page | No React UI to browse/search the OV context store | Users can't interact with `viking://` from the web |
| No tests | Zero test coverage for any OV code | Can't validate anything works |
| No `.env` wiring | `OPENVIKING_URL` not in `.env.example` | New devs won't know to configure it |
| No tiered retrieval | Only uses `find` (flat search), never `search` (hierarchical L0/L1/L2) | Misses the main value prop of OV |
| No session management | Nothing creates/commits OV sessions during scan cycles | No auto-memory extraction happening |
| No resource ingestion pipeline | Fetchers don't push filings into OV after fetch | OV store stays empty |

---

## Phase 1 -- Infrastructure (make it runnable)

### 1a. Docker Compose service

Add to `compose.yml`:

```yaml
openviking:
  image: volcengine/openviking:latest
  ports:
    - "1933:1933"
  volumes:
    - openviking_data:/data
  environment:
    - OPENVIKING_EMBEDDING_PROVIDER=openai
    - OPENVIKING_EMBEDDING_MODEL=text-embedding-3-large
    - OPENVIKING_VLM_PROVIDER=litellm
    - OPENVIKING_VLM_MODEL=claude-sonnet-4-6-20250514
    - OPENAI_API_KEY=${OPENAI_API_KEY}
    - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:1933/health"]
    interval: 10s
    timeout: 5s
    retries: 5
```

Add `OPENVIKING_URL=http://localhost:1933` to `.env.example`. Make `backend` depend on `openviking`.

### 1b. Tests for existing bridge

Create `backend/tests/test_openviking.py`:
- Mock `SyncHTTPClient` to test `ov_search`, `ov_read`, etc.
- Test the FastAPI proxy routes with `TestClient` + httpx mocks
- Test `is_available()` returns `False` when server is down

---

## Phase 2 -- Skill Layer (connect OV to the agent framework)

### 2a. `OpenVikingSearchSkill`

File: `backend/app/naturalsentinel/skills/openviking_search.py`

- Permissions: `Permission.FETCH_NETWORK | Permission.MEMORY_READ`
- Params: `query`, `target_uri`, `limit`
- Calls OV bridge `ov_search()` or hierarchical `search`
- Returns results as `SkillResult`
- Graceful fallback if OV is unavailable

### 2b. `OpenVikingIngestSkill`

File: `backend/app/naturalsentinel/skills/openviking_ingest.py`

- Permissions: `Permission.FETCH_NETWORK | Permission.MEMORY_WRITE`
- Accepts a filing dict or URL, pushes to OV via `ov_add_resource()`
- Organizes under `viking://resources/regulatory/{domain}/{filing_id}`
- Returns `root_uri` of ingested content

### 2c. Register in `ALL_SKILLS`

Add both instances to `backend/app/naturalsentinel/skills/__init__.py`.

---

## Phase 3 -- Dual-Storage Memory (the real integration)

### 3a. `HybridMemoryStore`

Create a store that owns both `PgMemoryStore` and an OV client:
- `store_episodic()` writes to both PG and OV
- `recall()` queries both, merges + deduplicates + ranks results

Update `api/deps.py` `get_ns_memory()` to return hybrid store when `OPENVIKING_URL` is configured, fall back to pure PG otherwise.

### 3b. Wire into scan pipeline

Modify `ScanCycleSkill` or `StoreMemorySkill` to also invoke `OpenVikingIngestSkill` after PG storage. Every analyzed filing automatically lands in `viking://resources/regulatory/`.

---

## Phase 4 -- Session Management (auto-memory extraction)

### 4a. `OpenVikingSessionSkill`

Manages OV session lifecycle:
- `create_session()` at scan start
- `add_message()` for each filing analysis (LLM prompt/response as turns)
- `commit_session()` at scan end

On commit, OV auto-extracts long-term memories (entities, patterns) into `viking://user/` and `viking://agent/`.

### 4b. Hook into `ScanCycleSkill`

Before scan loop: `openviking_session:create`
After each analysis: `openviking_session:add_message`
After loop: `openviking_session:commit`

---

## Phase 5 -- Tiered Retrieval (L0/L1/L2)

### 5a. Enhance `BuildContextSkill`

Change from flat recall to tiered:
1. Query OV with `search()` (hierarchical, not just `find()`)
2. Scan L0 abstracts to assess relevance cheaply
3. Promote relevant hits to L1 overview
4. Load L2 full content only for top 2-3 hits
5. Assemble context string within token budget

83-96% reduction in input token cost vs. loading full documents.

### 5b. Extend the OV bridge

Add to `mcp/openviking.py`:
- `ov_search_hierarchical()` -- full `search` API
- `ov_abstract()` -- reads L0 for a URI
- `ov_overview()` -- reads L1 for a URI

---

## Phase 6 -- Frontend

### 6a. OpenViking page

File: `frontend/src/routes/_layout/openviking.tsx`

- Filesystem browser -- tree view of `viking://` URIs
- Search bar -- semantic search
- Content viewer -- L0/L1/L2 tabs for any resource
- Ingest form -- add URL or file
- Health indicator

### 6b. Regenerate TS client

`bash scripts/generate-client.sh`

### 6c. Sidebar entry

Add to `baseItems` in `AppSidebar.tsx`.

---

## Phase 7 -- Testing & Hardening

| Test | What |
|------|------|
| Unit: bridge functions | Mock `SyncHTTPClient`, verify correct API calls |
| Unit: skills | Mock OV bridge, verify `SkillResult` shape |
| Unit: hybrid store | Mock both PG session and OV client, verify dual writes |
| Integration: proxy routes | `TestClient` + mock httpx, verify request forwarding |
| Integration: scan pipeline | Full scan with mock provider + mock OV, verify filings land in both stores |
| E2E: Playwright | Navigate to `/openviking`, search, browse, ingest |

---

## Architecture Decisions

1. **OV as secondary, not primary** -- PG remains source of truth. OV is enrichment. If OV is down, everything still works.
2. **Feature-flag via config** -- Check `settings.OPENVIKING_URL` before any OV call. If empty, skip OV entirely.
3. **Don't replace Qdrant yet** -- OV's vector index can eventually replace Qdrant, but migrate incrementally.
4. **Session-per-scan, not session-per-request** -- Each `scan_cycle` creates one OV session.
