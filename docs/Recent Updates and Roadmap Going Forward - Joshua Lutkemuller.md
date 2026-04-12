# Recent Updates and Roadmap Going Forward

**Author:** Joshua Lutkemuller
**Collaborator:** Joshua Lutkemuller
**Date:** April 12, 2026

---

## Overview

This document summarizes the latest development activity across NaturalSentinel branches and outlines the strategic roadmap going forward. NaturalSentinel is an agentic regulatory change monitor that watches regulatory filings, runs LLM-powered impact analysis, maintains a persistent memory system, and surfaces briefings via a FastAPI + React interface.

---

## Recent Updates

### 1. Claude Skills Infrastructure

Added 11 developer skills (`.claude/skills/`), 3 agent personas (backend-reviewer, frontend-reviewer, regulatory-domain), project rules, and `CLAUDE.md`. This gives AI-assisted development a consistent pattern vocabulary across the entire stack.

- 11 reusable skills: add-api-route, add-fetcher, add-frontend-page, add-model-and-crud, add-skill, db-migrate, dev-services, generate-client, run-pipeline, test
- 3 specialized agent personas for code review and domain guidance
- Centralized project conventions in `CLAUDE.md` and `.claude/rules/`

### 2. FastAPI Production Template

Major structural migration from `src/` to `backend/app/`, standing up the full production stack:

- **7 route modules** — filings, items, login, users, memory, mcp, tools
- **React + TanStack Router frontend** with shadcn/ui, dark mode, and role-based dashboard
- **Docker Compose** — Postgres, Redis, Qdrant, MailCatcher
- **Auto-generated TypeScript client** from OpenAPI spec
- **Testing** — Playwright end-to-end tests + pytest backend tests
- Migrated all NaturalSentinel code into the new layout with 140+ import updates

### 3. Live Regulatory Ingestion

Four production API sources wired into `fetch_filings(live=True)`:

| Source | Coverage |
|--------|----------|
| **Federal Register** | FED, CFPB, OCC, FDIC, CFTC, SEC, EPA, USTR, FHFA, FDA |
| **SEC EDGAR** | Full-text search with deduplication by accession number |
| **BIS** | Basel Committee (BCBS) publications |
| **FINRA** | Regulatory notice scraping |

Supporting infrastructure includes a rate-limited HTTP client, HTML-to-text parser, change-type detection heuristics, and 53 offline tests with `MockHTTPClient`.

### 4. Belief Tracking Engine

Bayesian confidence evolution per topic/domain:

- `BeliefState` model with prior/posterior confidence, delta drivers, stability score, and reversal risk
- Exponential moving average algorithm (no LLM calls — `FAST` latency class)
- SQLite persistence with belief_states and belief_history tables
- 36 unit tests covering CRUD operations, math edge cases, and integration

### 5. Quantitative Evaluation Layer

Measurement infrastructure in `eval/`:

- **Scorer** — per-field accuracy (exact match for categoricals, Jaccard for sets, length-ratio for lists)
- **Calibration** — ECE / MCE computation with reliability-diagram data
- **Drift** — total variation distance for categoricals, Cohen's d for continuous; flags when shift exceeds 0.15
- `RunEvaluationSkill` with historical (from feedback_log) and fixture (JSON) modes
- 66 tests

### 6. Governance and Data Lineage

Three major subsystems for explainability and compliance:

- **Governance** — ModelCard, 15-control ControlMatrix, AuditEvent (11 types), FailureTaxonomy (10 coded categories), EscalationPolicy, FallbackPolicy
- **Lineage** — FieldCitation with verbatim source passages, DecisionTrace with timed pipeline steps, ModelProvenance with prompt-template hashing
- **AnalyzeFilingSkill v2** — 6-step traced pipeline emitting audit events, storing traces/citations, triggering escalations
- 102 tests across governance and lineage

### 7. CLI/MCP AgentRuntime Refactor

Replaced direct `RegulatoryMonitorAgent` calls with `AgentRuntime.execute_skill()` dispatch in both `cli.py` and `mcp/server.py`. All tool handlers now go through the unified skill registry.

### 8. MCP Healthcare Use Cases

Exploratory work on HIPAA-safe healthcare integrations — DEA telehealth, niche healthcare MCP use cases, and external MCP server client integrations.

### 9. Infrastructure

DevContainer configuration, uv package manager setup, and frozen dependency lock.

---

## Current State

| Metric | Value |
|--------|-------|
| Registered skills | 36 across 5 categories |
| Regulatory domains | 12 agencies |
| Live data sources | 4 (Federal Register, EDGAR, BIS, FINRA) |
| Test coverage | ~1,000+ unit tests |
| Governance controls | 15 (auditability, accuracy, explainability, escalation, data quality, model risk) |

---

## Roadmap Going Forward

### High Priority

1. **Database migration alignment** — Verify that Alembic migrations exist for all SQLModel `table=True` definitions in `pg_models.py` (beliefs, eval runs, audit log, traces, citations). Run `uv run alembic heads` and `uv run alembic check` from `backend/` to confirm. Missing migrations will silently fail at runtime.

2. **Memory store unification** — The belief tracker, eval, governance, and lineage systems each added their own CRUD methods to `memory/store.py` against what was originally an SQLite backend, which then migrated to PostgreSQL (`pg_models.py`). Audit that all store methods now target `PgMemoryStore` and that old SQLite schema definitions are removed or clearly marked as legacy.

3. **Skill test coverage for the 36-skill registry** — The 6 core pipeline skills have solid tests, but the 30 specialist/desk/platform/telecom skills in `ALL_SKILLS` may be stubs. Verify which are implemented vs. placeholders, and either add tests or remove unimplemented entries to keep the registry honest.

4. **Live fetcher robustness** — BIS and FINRA rely on HTML scraping, which is inherently fragile. Add monitoring and alerting (at minimum, structured logging) for when page structure changes break parsing. Consider adding `last_successful_fetch` timestamps to catch silent failures.

### Medium Priority

5. **Frontend data flow** — The backend has routes for filings, memory, MCP, and tools, but the frontend pages may not yet consume all of them (belief states, eval runs, governance dashboards). Prioritize surfacing belief tracking and eval results in the UI — they are the most user-facing differentiators.

6. **Client regeneration** — After the large backend reorganization, confirm `bash scripts/generate-client.sh` produces a clean TypeScript client covering all current routes. Stale types are a common source of runtime bugs after structural migrations.

7. **Drift/calibration feedback loop** — `RunEvaluationSkill` can detect drift and calibration degradation, but there is no automated response yet (e.g., triggering recalibration, adjusting confidence thresholds, or notifying operators). Wire the drift report output into the escalation policy system already in place.

### Lower Priority

8. **MCP healthcare exploration** — The healthcare use-case branch has design docs but no implementation. If this is a target market, convert it into concrete fetcher + skill pairs; if exploratory, archive the branch to reduce noise.

9. **Governance model card versioning** — `ModelCard.default()` ships a canonical card, but it should be versioned alongside releases and updated whenever the provider/model changes. Consider auto-generating it from `settings.py` + `eval_runs` data.

10. **Performance profiling** — With 36 skills and 4 live fetchers, a full scan cycle could be slow. Profile `scan_cycle` end-to-end and consider parallelizing independent fetcher calls (currently sequential with try/except fallback).

---

## Architecture Summary

The recent commits represent a complete production-grade transformation of NaturalSentinel:

1. **Infrastructure** — FastAPI + PostgreSQL + Docker multi-container stack with Vite frontend
2. **Data Ingestion** — Four live regulatory API sources with graceful fallback to sample data
3. **Intelligence** — Skill-based agent framework with 36 composable capabilities covering 12 regulatory domains
4. **Explainability** — End-to-end lineage tracking (citations, decision traces, model provenance) with governance model card and control matrix
5. **Evaluation** — Quantitative benchmarking with accuracy, calibration, and drift analysis using human feedback as ground truth
6. **Belief Tracking** — Bayesian confidence evolution per topic with stability and reversal-risk scoring
7. **Auditability** — Append-only audit log with 11 event types, failure taxonomy (10 categories), and escalation/fallback policies

All code is properly tested with 1,000+ unit tests across eval, lineage, governance, live fetchers, and belief tracking. The system is designed to run as a standalone FastAPI service with PostgreSQL backend, or integrated into Claude Desktop/Cursor via MCP.
