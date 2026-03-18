# NaturalSentinel Skill Catalogue

> **Branch:** `claude/expand-naturalsentinel-agents-j6oEQ`
> **Base:** `main` @ `0a51d23` (Merge PR #3 — financial desk agents)
> **Source:** `src/naturalsentinel/skills/`
> **Registry:** `src/naturalsentinel/skills/__init__.py` → `ALL_SKILLS` (25 skills)

---

## Overview

Every capability in NaturalSentinel is a **Skill** — a self-contained unit with declared permissions, a typed parameter schema, latency class, and dependency graph. Skills are registered in `ALL_SKILLS` and executed by `AgentRuntime`, which enforces permission policies, token budgets, and records a full audit trail.

### Permission flags

| Flag | Meaning |
|------|---------|
| `LLM_READ` | Call an LLM for inference (read-only) |
| `LLM_WRITE` | Call an LLM to generate stored content |
| `MEMORY_READ` | Read from the SQLite memory store |
| `MEMORY_WRITE` | Write to the SQLite memory store |
| `STATE_READ` | Read dedup / checkpoint state |
| `STATE_WRITE` | Write dedup / checkpoint state |
| `FETCH_LOCAL` | Read from local sample / cached data |
| `FETCH_NETWORK` | Make outbound HTTP requests |
| `FILE_READ` / `FILE_WRITE` | Filesystem access |
| `HUMAN_INPUT` | Request user confirmation |

### Latency classes

| Class | Expected duration |
|-------|------------------|
| `instant` | < 100 ms — pure computation |
| `fast` | < 2 s — local DB / cached data |
| `moderate` | 2–15 s — single LLM call |
| `slow` | 15–60 s — multiple LLM calls |
| `batch` | > 60 s — full scan cycle |

---

## Skill Groups

- [Core Pipeline](#core-pipeline) — 9 skills
- [Intelligence / Analytics](#intelligence--analytics) — 6 skills
- [Specialist / Desk Skills](#specialist--desk-skills) — 10 skills

---

## Core Pipeline

These skills form the primary data flow: fetch → dedup → contextualise → analyse → store → brief.

---

### `fetch_filings`

Retrieve regulatory filings from configured sources (SEC, CFPB, Fed, FDA, EPA, USTR). Currently reads from curated sample data; a production deployment would connect to live APIs (EDGAR, Federal Register, etc.).

| Property | Value |
|----------|-------|
| Version | 1.0.0 |
| Permissions | `FETCH_LOCAL` |
| Latency | `fast` |
| Cacheable | Yes |
| Token budget | 0 |
| Tags | `fetch`, `data-source`, `regulatory` |

**Parameters**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `domains` | `list[str]` | No | `[]` | Agency codes to fetch (e.g. `['sec', 'fda']`). Empty = all. |
| `since_days` | `int` | No | `30` | Look-back window in days. |

**Returns:** `list[dict]` — serialised `RegulatoryFiling` objects.

---

### `analyze_filing`

Send a single regulatory filing to the LLM for structured impact analysis. Returns severity, affected business lines, compliance deadlines, action items, and a confidence score. Optionally enriched with memory context from `build_context`.

| Property | Value |
|----------|-------|
| Version | 1.0.0 |
| Permissions | `LLM_READ`, `LLM_WRITE` |
| Latency | `moderate` |
| Cacheable | No |
| Token budget | 4 096 |
| Tags | `analysis`, `llm`, `core` |
| Dependencies | `build_context` |

**Parameters**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `filing` | `dict` | **Yes** | — | Serialised `RegulatoryFiling` with `id`, `title`, `domain`, `raw_text`, etc. |
| `memory_context` | `str` | No | `""` | Pre-built memory context block to append to the prompt. |

**Returns:** `dict` — parsed impact assessment: `severity`, `affected_business_lines`, `affected_regulations`, `compliance_deadline`, `action_items`, `risk_summary`, `confidence`.

---

### `recall_memory`

Search persistent memory for relevant past analyses, entity knowledge, or correction precedents using TF-IDF keyword similarity.

| Property | Value |
|----------|-------|
| Version | 1.0.0 |
| Permissions | `MEMORY_READ` |
| Latency | `fast` |
| Cacheable | No |
| Token budget | 4 096 |
| Tags | `memory`, `search`, `read-only` |

**Parameters**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `query` | `str` | **Yes** | — | Natural-language search query. |
| `memory_type` | `str` | No | `null` | Filter: `episodic`, `entity`, or `precedent`. |
| `top_k` | `int` | No | `5` | Max results to return. |

**Returns:** `list[dict]` — matching memory records with relevance scores.

---

### `store_memory`

Persist a filing and its impact assessment as episodic memory. Automatically extracts entity relations (`filing → affects_business → line`, `filing → modifies_regulation → reg`).

| Property | Value |
|----------|-------|
| Version | 1.0.0 |
| Permissions | `MEMORY_WRITE` |
| Latency | `fast` |
| Cacheable | No |
| Token budget | 4 096 |
| Tags | `memory`, `write`, `persistence` |

**Parameters**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `filing_id` | `str` | **Yes** | — | Unique filing identifier. |
| `filing` | `dict` | **Yes** | — | Serialised filing data. |
| `impact` | `dict` | **Yes** | — | Impact assessment data. |

**Returns:** `dict` — confirmation with updated memory stats.

---

### `record_feedback`

Record a human correction on a past analysis. Creates a `precedent` memory record that future `analyze_filing` calls will retrieve as context, enabling the agent to learn from corrections over time.

| Property | Value |
|----------|-------|
| Version | 1.0.0 |
| Permissions | `MEMORY_READ`, `MEMORY_WRITE` |
| Latency | `fast` |
| Cacheable | No |
| Token budget | 4 096 |
| Tags | `feedback`, `learning`, `memory`, `write` |

**Parameters**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `filing_id` | `str` | **Yes** | — | The filing ID to correct. |
| `field` | `str` | **Yes** | — | Which field to correct (`severity`, `affected_business_lines`, etc.). |
| `old_value` | `str` | **Yes** | — | The current / wrong value. |
| `new_value` | `str` | **Yes** | — | The correct value. |
| `reason` | `str` | No | `""` | Why this correction is needed. |

**Returns:** `dict` — confirmation.

---

### `build_context`

Query memory for relevant past analyses, entity knowledge, and correction precedents, then format them into a context block for LLM prompt injection. Used by `analyze_filing` and specialist desk skills.

| Property | Value |
|----------|-------|
| Version | 1.0.0 |
| Permissions | `MEMORY_READ` |
| Latency | `fast` |
| Cacheable | No |
| Token budget | 4 096 |
| Tags | `memory`, `context`, `read-only`, `prompt-engineering` |

**Parameters**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `domain` | `str` | **Yes** | — | Regulatory domain code (`sec`, `cfpb`, etc.). |
| `filing_text` | `str` | **Yes** | — | The filing text to find context for. |
| `max_tokens` | `int` | No | `1500` | Soft cap on context length. |

**Returns:** `str` — formatted memory context block (empty string if no relevant memories found).

---

### `detect_duplicates`

Filter a list of filings against previously-seen IDs stored in the state file. Returns only new (unseen) filings and optionally marks them as seen for future runs.

| Property | Value |
|----------|-------|
| Version | 1.0.0 |
| Permissions | `STATE_READ`, `STATE_WRITE` |
| Latency | `instant` |
| Cacheable | No |
| Token budget | 4 096 |
| Tags | `dedup`, `state`, `filtering` |

**Parameters**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `filings` | `list[dict]` | **Yes** | — | List of serialised filings to check. |
| `mark_seen` | `bool` | No | `true` | Whether to update state with the new IDs. |

**Returns:** `dict` — `{new_filings: list[dict], duplicates_skipped: int}`.

---

### `generate_briefing`

Produce an executive-level regulatory briefing by reading recent analyses from memory and synthesising them into prose via the LLM. Audience-aware: adjusts depth and framing for board, compliance team, or general counsel.

| Property | Value |
|----------|-------|
| Version | 1.0.0 |
| Permissions | `LLM_READ`, `MEMORY_READ` |
| Latency | `moderate` |
| Cacheable | No |
| Token budget | 8 192 |
| Tags | `output`, `llm`, `briefing`, `synthesis` |
| Dependencies | `recall_memory` |

**Parameters**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `audience` | `str` | No | `"executive leadership"` | Target audience (`board`, `compliance_team`, `general_counsel`). |
| `limit` | `int` | No | `10` | Max number of recent analyses to include. |

**Returns:** `str` — formatted briefing text.

---

### `scan_cycle`

Execute a complete regulatory monitoring cycle: **fetch → deduplicate → build context → analyse → store**. This is the primary orchestration entrypoint that composes lower-level skills into a coherent batch workflow.

| Property | Value |
|----------|-------|
| Version | 1.0.0 |
| Permissions | `LLM_READ`, `LLM_WRITE`, `MEMORY_READ`, `MEMORY_WRITE`, `STATE_READ`, `STATE_WRITE`, `FETCH_LOCAL` |
| Latency | `batch` |
| Cacheable | No |
| Token budget | 50 000 |
| Tags | `orchestration`, `core`, `batch` |
| Dependencies | `fetch_filings`, `detect_duplicates`, `build_context`, `analyze_filing`, `store_memory` |

**Parameters**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `domains` | `list[str]` | No | `[]` | Agency codes to scan. Empty = all. |
| `since_days` | `int` | No | `30` | Look-back window. |

**Returns:** `dict` — `{results: list[dict], stats: {total_fetched, new_analyzed, duplicates_skipped, errors}}`.

---

## Intelligence / Analytics

These skills operate on data already in memory — no fetching or primary LLM analysis. They surface patterns, alerts, and reports across the accumulated history.

---

### `alert_threshold`

Scan stored analyses and raise alerts for any filing whose severity meets or exceeds a configured threshold. Returns a prioritised alert report with urgency tiers: **immediate**, **48-hour**, and **7-day**.

| Property | Value |
|----------|-------|
| Version | 1.0.0 |
| Permissions | `MEMORY_READ` |
| Latency | `fast` |
| Cacheable | No |
| Token budget | 4 096 |
| Tags | `alert`, `monitoring`, `threshold`, `read-only` |

**Parameters**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `threshold` | `str` | No | `"high"` | Minimum severity to alert on: `low`, `medium`, `high`, or `critical`. |
| `limit` | `int` | No | `50` | Maximum number of recent analyses to inspect. |

**Returns:** `dict` — `{alerts: list[dict], summary: dict}`. Each alert includes `filing_id`, `title`, `domain`, `severity`, `deadline`, `action_items`, `urgency_tier`, `affected_business_lines`.

---

### `compliance_deadline`

Extract compliance deadlines from stored analyses and return a prioritised calendar view. Items are categorised as `overdue`, `due_soon` (within the look-ahead window), or `upcoming`. Suitable for compliance calendars, dashboards, and automated reminders.

| Property | Value |
|----------|-------|
| Version | 1.0.0 |
| Permissions | `MEMORY_READ` |
| Latency | `fast` |
| Cacheable | No |
| Token budget | 4 096 |
| Tags | `deadline`, `calendar`, `compliance`, `read-only` |

**Parameters**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `look_ahead_days` | `int` | No | `30` | Number of days to consider "due soon". |
| `domain_filter` | `str` | No | `""` | Limit to a single agency code (e.g. `sec`). Empty = all. |
| `limit` | `int` | No | `100` | Maximum number of analyses to scan. |

**Returns:** `dict` — `{overdue: list, due_soon: list, upcoming: list, no_deadline: list, summary: dict}`. Each item includes `filing_id`, `title`, `domain`, `severity`, `deadline`, `days_until`, `action_items`.

---

### `trend_analysis`

Analyse historical filing data in memory to detect regulatory trends. Splits the history into two temporal windows (older half vs. recent half) and compares per-domain severity distributions to identify escalating or de-escalating regulatory pressure.

| Property | Value |
|----------|-------|
| Version | 1.0.0 |
| Permissions | `MEMORY_READ`, `LLM_READ` |
| Latency | `moderate` |
| Cacheable | No |
| Token budget | 4 096 |
| Tags | `trends`, `analysis`, `patterns`, `intelligence` |

**Parameters**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `limit` | `int` | No | `50` | Number of recent analyses to include in the trend window. |
| `include_narrative` | `bool` | No | `true` | Generate an LLM narrative summary (requires `LLM_READ`). |

**Returns:** `dict` — `{statistics: dict, trend_signals: list[dict], narrative: str|null}`. Each `trend_signal` has `domain`, `signal` (`escalating|stable|de-escalating`), `avg_severity_older`, `avg_severity_recent`, `delta`, `filing_count`.

---

### `cross_domain_correlation`

Identify business lines simultaneously regulated by multiple agencies within stored analyses. Returns intersection maps showing cross-agency compound compliance burden with an optional LLM assessment.

| Property | Value |
|----------|-------|
| Version | 1.0.0 |
| Permissions | `MEMORY_READ`, `LLM_READ` |
| Latency | `moderate` |
| Cacheable | No |
| Token budget | 4 096 |
| Tags | `cross-domain`, `correlation`, `analysis`, `multi-agency` |

**Parameters**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `min_domains` | `int` | No | `2` | Minimum distinct domains a business line must appear in to flag. |
| `limit` | `int` | No | `100` | Number of recent analyses to inspect. |
| `include_assessment` | `bool` | No | `true` | Generate LLM assessment of compound burden (requires `LLM_READ`). |

**Returns:** `dict` — `{intersections: list[dict], assessment: str|null}`. Each intersection includes `business_line`, `domains`, `combined_action_items`, `combined_regulations`, `max_severity`, `filing_count`.

---

### `export_report`

Generate a structured compliance report from stored analyses. Supports three output formats: `markdown` (human-readable), `json` (machine-readable), and `csv` (tabular, for BI tools). No LLM calls — deterministic output.

| Property | Value |
|----------|-------|
| Version | 1.0.0 |
| Permissions | `MEMORY_READ` |
| Latency | `fast` |
| Cacheable | No |
| Token budget | 4 096 |
| Tags | `export`, `reporting`, `output`, `read-only` |

**Parameters**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `format` | `str` | No | `"markdown"` | Output format: `markdown`, `json`, or `csv`. |
| `limit` | `int` | No | `25` | Maximum number of recent analyses to include. |
| `domain_filter` | `str` | No | `""` | Limit to a single agency code. Empty = all. |
| `min_severity` | `str` | No | `"low"` | Only include analyses at or above this severity. |

**Returns:** `dict` — `{format: str, content: str, row_count: int, metadata: dict}`.

---

### `regime_detection`

Identify which macro-prudential regulatory regimes are **active** based on signal language patterns across recent filings. Uses a two-pass approach — fast keyword scoring (no LLM cost) followed by optional LLM synthesis — to produce phase assessments and transition signals.

The output **informs rather than prescribes**: it names which regimes are consistent with observed regulatory language and characterises each regime's current phase, without recommending specific firm actions.

See [`docs/REGIME_ARCHETYPES.md`](REGIME_ARCHETYPES.md) for the full taxonomy of 10 regime archetypes and their signal vocabularies.

| Property | Value |
|----------|-------|
| Version | 1.0.0 |
| Permissions | `MEMORY_READ`, `LLM_READ` |
| Latency | `moderate` |
| Cacheable | No |
| Token budget | 4 096 |
| Tags | `regime`, `macro-prudential`, `classification`, `cycle-detection`, `signal` |

**Parameters**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `window_days` | `int` | No | `90` | Look-back window in days for filing analysis. |
| `domains` | `list[str]` | No | `null` | Filter to specific regulatory domains. `null` = all. |
| `signal_threshold` | `float` | No | `0.10` | Minimum normalised signal strength (0–1) to report a regime as active. |
| `raw_filings` | `list[dict]` | No | `null` | Optional raw filing dicts for offline / test use (bypasses memory). |

**Returns:** `dict`

```json
{
  "active_regimes": [
    {
      "regime_id": "prudential_capital_tightening",
      "regime_label": "Prudential Capital Tightening Cycle",
      "signal_strength": 0.72,
      "evidence_count": 18,
      "signal_terms_found": ["output floor", "gsib surcharge", "cet1 requirement"],
      "regulatory_bodies_active": ["BASEL", "FED"],
      "regime_phase": "acceleration",
      "summary": "Basel IV output floor language is appearing at accelerating frequency..."
    }
  ],
  "dormant_regimes": ["agency_gse_reform", "consumer_fair_lending_scrutiny"],
  "regime_transitions": [
    {
      "regime_id": "digital_asset_regulatory_capture",
      "transition": "newly_active",
      "basis": "SAB 122 and stablecoin guidance language appearing for first time"
    }
  ],
  "analysis_window_days": 90,
  "filings_analyzed": 25,
  "confidence": 0.81,
  "summary": "The current filing landscape is consistent with a mid-acceleration..."
}
```

---

## Specialist / Desk Skills

These skills apply deep domain expertise to a single filing. Each requires a `filing` dict as input (plus optional `memory_context`) and returns a structured assessment targeting a specific desk or function.

All specialist skills share this base signature:

```python
{
  "filing": dict,          # required — serialised RegulatoryFiling
  "memory_context": str    # optional — from build_context skill
}
```

Permissions: `LLM_READ | LLM_WRITE | MEMORY_READ` · Latency: `moderate` · Cacheable: No

---

### `capital_impact`

Analyse a regulatory filing for capital implications — estimates RWA delta, SLR impact, leverage ratio effects, and output floor consequences. Designed for Capital Optimization desks and quant teams building capital allocation models.

**Tags:** `capital`, `rwa`, `slr`, `leverage`, `optimization`, `basel`

**Returns schema:**

| Field | Type | Description |
|-------|------|-------------|
| `rwa_impact_direction` | `increase\|decrease\|neutral\|unknown` | Direction of RWA change |
| `rwa_pct_change_estimate` | `float` | Estimated RWA change in basis points |
| `slr_impact_direction` | `increase\|decrease\|neutral\|unknown` | Supplementary leverage ratio direction |
| `leverage_ratio_impact` | `tightens\|loosens\|neutral\|unknown` | Leverage ratio constraint direction |
| `output_floor_relevance` | `bool` | Whether the output floor is implicated |
| `affected_capital_metrics` | `list[str]` | e.g. `["CET1", "T1 leverage", "SLR"]` |
| `capital_cost_per_trade_bps` | `float` | Estimated incremental capital cost per trade |
| `optimization_constraint_changes` | `list[str]` | Binding constraint changes for optimizers |
| `model_recalibration_required` | `bool` | Whether capital models need recalibration |
| `confidence` | `float` | 0–1 |
| `summary` | `str` | 2–3 sentence narrative |

---

### `model_risk_assessment`

Identify which internal quantitative models require re-validation or documentation updates based on a regulatory filing. Maps SR 11-7 obligations to specific model types — optimization, ML, pricing, risk — used by data science teams.

**Tags:** `model-risk`, `sr11-7`, `validation`, `ml`, `optimization`, `data-science`

**Additional parameter:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `model_inventory` | `list[str]` | No | `[]` | Model names/types in scope for this assessment. |

**Returns schema:**

| Field | Type | Description |
|-------|------|-------------|
| `models_requiring_revalidation` | `list[str]` | Specific models by name / type |
| `validation_tier` | `str` | SR 11-7 tier classification |
| `documentation_updates_required` | `list[str]` | Required doc changes |
| `challenger_model_required` | `bool` | Whether a challenger model is needed |
| `drift_monitoring_required` | `bool` | Whether ongoing drift monitoring is triggered |
| `retraining_triggers` | `list[str]` | Conditions that would require retraining |
| `governance_actions` | `list[str]` | MRC/board governance steps |
| `examiner_readiness_gaps` | `list[str]` | Gaps vs. examiner expectations |
| `urgency` | `str` | `immediate\|30-day\|90-day\|annual` |
| `confidence` | `float` | 0–1 |
| `summary` | `str` | |

---

### `securities_financing_analysis`

Analyse regulatory changes affecting repo, reverse repo, securities lending, and TBA markets. Surfaces impacts on collateral schedules, haircut matrices, rehypothecation limits, settlement frameworks, and SFTR reporting.

**Tags:** `securities-lending`, `repo`, `tba`, `collateral`, `haircut`, `prime`, `sftr`

**Returns schema:**

| Field | Type | Description |
|-------|------|-------------|
| `rehypothecation_impact` | `str` | Direction and nature of rehypothecation constraint |
| `haircut_changes` | `list[str]` | Specific haircut changes by collateral type |
| `collateral_eligibility_changes` | `list[str]` | Newly eligible or excluded collateral |
| `repo_market_impact` | `str` | Overall repo market impact description |
| `settlement_framework_changes` | `list[str]` | Settlement / fails rule changes |
| `sftr_reporting_changes` | `list[str]` | SFTR schema or methodology changes |
| `margin_requirement_changes` | `list[str]` | IM / VM changes |
| `prime_brokerage_impacts` | `list[str]` | Prime desk-specific impacts |
| `desk_action_items` | `list[str]` | Prioritised action list |
| `confidence` | `float` | 0–1 |
| `summary` | `str` | |

---

### `liquidity_ratio_analysis`

Analyse regulatory changes for HQLA classification impacts, LCR/NSFR treatment changes, and balance sheet liquidity implications. Feeds directly into ALM models and balance sheet optimizers for Financing Solutions desks.

**Tags:** `liquidity`, `lcr`, `nsfr`, `hqla`, `alm`, `balance-sheet`, `financing`

**Returns schema:**

| Field | Type | Description |
|-------|------|-------------|
| `hqla_classification_changes` | `list[str]` | Changes to L1/L2A/L2B asset eligibility |
| `lcr_impact_direction` | `increase\|decrease\|neutral\|unknown` | |
| `lcr_delta_estimate_pct` | `float` | Estimated LCR ratio delta in percentage points |
| `nsfr_impact_direction` | `increase\|decrease\|neutral\|unknown` | |
| `nsfr_asf_rsf_changes` | `list[str]` | Available / required stable funding changes |
| `liquidity_buffer_implications` | `list[str]` | Buffer sizing implications |
| `funding_cost_impact` | `str` | Directional funding cost narrative |
| `balance_sheet_optimization_constraints` | `list[str]` | New optimizer constraints |
| `action_items` | `list[str]` | |
| `confidence` | `float` | 0–1 |
| `summary` | `str` | |

---

### `agency_mortgage_analysis`

Parse FHFA, Fannie Mae, Freddie Mac, and Ginnie Mae regulatory changes for Agency Lending desk impacts. Surfaces conforming limit changes, g-fee adjustments, collateral haircut updates, CRT programme changes, and TBA eligibility impacts.

**Tags:** `agency-lending`, `fhfa`, `gse`, `fannie`, `freddie`, `tba`, `mbs`, `crt`

**Returns schema:**

| Field | Type | Description |
|-------|------|-------------|
| `conforming_limit_changes` | `list[str]` | New limits by loan type / geography |
| `gfee_adjustments` | `list[str]` | Guarantee fee changes |
| `collateral_haircut_updates` | `list[str]` | Agency collateral haircut changes |
| `crt_program_changes` | `list[str]` | Credit risk transfer programme updates |
| `tba_eligibility_changes` | `list[str]` | TBA market eligibility changes |
| `prepayment_model_implications` | `list[str]` | Prepayment model recalibration triggers |
| `hedging_implications` | `list[str]` | Duration / convexity hedging changes |
| `agency_lending_program_impacts` | `list[str]` | Programme-level impacts |
| `desk_action_items` | `list[str]` | |
| `confidence` | `float` | 0–1 |
| `summary` | `str` | |

---

### `counterparty_risk_analysis`

Analyse SA-CCR, initial margin (SIMM / UMR), CVA capital charge, and counterparty credit risk framework changes. Maps regulatory changes to EAD impacts, IM requirement changes, CVA capital deltas, and netting set modifications — actionable for Prime Lending and XVA desks.

**Tags:** `counterparty-risk`, `sa-ccr`, `simm`, `cva`, `ead`, `xva`, `prime-lending`

**Returns schema:**

| Field | Type | Description |
|-------|------|-------------|
| `sa_ccr_ead_impact` | `str` | SA-CCR EAD direction and magnitude |
| `supervisory_factor_changes` | `list[str]` | Supervisory factor changes by asset class |
| `initial_margin_change_pct` | `float` | Estimated IM requirement change in % |
| `cva_capital_impact` | `float` | CVA capital change in basis points |
| `mva_impact` | `str` | Margin valuation adjustment direction |
| `netting_set_changes` | `list[str]` | Netting eligibility or set size changes |
| `counterparty_tier_impacts` | `list[str]` | Impacts by counterparty tier (bank, fund, corporate) |
| `ead_delta_direction` | `increase\|decrease\|neutral\|unknown` | |
| `xva_recalibration_required` | `bool` | |
| `action_items` | `list[str]` | |
| `confidence` | `float` | 0–1 |
| `summary` | `str` | |

---

### `regulatory_reporting_analysis`

Identify new or changed regulatory reporting obligations from a filing. Surfaces schema changes, new data elements, methodology updates, and deadline shifts for CCAR/DFAST, Form PF, FR Y-14, FINRA reporting, and SFTR — actionable for data engineering and reporting pipeline teams.

**Tags:** `reporting`, `ccar`, `dfast`, `form-pf`, `y-14`, `pipeline`, `data-engineering`

**Returns schema:**

| Field | Type | Description |
|-------|------|-------------|
| `new_reporting_obligations` | `list[str]` | New reports required |
| `changed_reporting_schedules` | `list[str]` | Frequency / timing changes |
| `schema_changes` | `list[str]` | Field additions, removals, or type changes |
| `methodology_updates` | `list[str]` | Calculation methodology changes |
| `system_pipeline_impacts` | `list[str]` | ETL / pipeline work required |
| `deadline_changes` | `list[str]` | Submission deadline shifts |
| `data_element_additions` | `list[str]` | New data elements required |
| `estimated_build_effort` | `str` | e.g. `"3–6 months"` |
| `action_items` | `list[str]` | |
| `confidence` | `float` | 0–1 |
| `summary` | `str` | |

---

### `optimization_constraint`

Translate a regulatory filing into formal optimization model constraints and objective function modifications. The most data-science-specific skill — converts regulatory language into constraint notation usable in balance sheet optimizers, capital allocation models, and portfolio construction frameworks.

**Tags:** `optimization`, `constraints`, `capital-allocation`, `balance-sheet`, `data-science`, `quant`

**Returns schema:**

| Field | Type | Description |
|-------|------|-------------|
| `constraint_type` | `str` | `equality\|inequality\|bound\|cardinality` |
| `constraint_expressions` | `list[dict]` | Each with `name`, `expression_text`, `constraint_direction`, `binding_scenario`, `affected_model_types` |
| `objective_function_impacts` | `list[str]` | Changes to the objective function |
| `portfolio_impacts` | `list[str]` | Portfolio-level constraint implications |
| `parameter_updates` | `list[str]` | Model parameter values to update |
| `model_types_affected` | `list[str]` | e.g. `["capital_optimizer", "sa-ccr_model"]` |
| `recalibration_urgency` | `str` | `immediate\|30-day\|quarterly\|annual` |
| `action_items` | `list[str]` | |
| `confidence` | `float` | 0–1 |
| `summary` | `str` | |

---

### `leveraged_lending_assessment`

Assess regulatory changes to leveraged lending guidelines, CLO risk retention rules, covenant requirements, and credit underwriting standards. Maps changes to portfolio thresholds, documentation requirements, and supervisory review triggers for Secured Lending and Financing Solutions desks.

**Tags:** `leveraged-lending`, `clo`, `risk-retention`, `covenants`, `underwriting`, `secured-lending`

**Returns schema:**

| Field | Type | Description |
|-------|------|-------------|
| `leverage_threshold_changes` | `list[str]` | Changes to leverage multiple thresholds |
| `definition_changes` | `list[str]` | Changes to what constitutes "leveraged" |
| `covenant_requirement_changes` | `list[str]` | Covenant package changes |
| `risk_retention_changes` | `list[str]` | CLO risk retention rule changes |
| `supervisory_review_triggers` | `list[str]` | New triggers for supervisory attention |
| `portfolio_classification_impacts` | `list[str]` | Reclassification of existing loans |
| `documentation_requirements` | `list[str]` | New documentation obligations |
| `exception_process_changes` | `list[str]` | Changes to policy exception process |
| `credit_policy_updates_required` | `bool` | Whether credit policy needs updating |
| `action_items` | `list[str]` | |
| `confidence` | `float` | 0–1 |
| `summary` | `str` | |

---

### `stress_testing_signal`

Extract stress scenario parameters and map them to desk-level P&L impacts. Parses CCAR / DFAST supervisory scenarios, Fed exploratory shocks, and EBA stress scenarios to identify macro variable paths, securities financing stresses, and hedging implications — actionable for stress testing teams and capital planning.

**Tags:** `stress-testing`, `ccar`, `dfast`, `scenario`, `macro`, `pl-impact`, `capital-planning`

**Returns schema:**

| Field | Type | Description |
|-------|------|-------------|
| `scenario_type` | `str` | `supervisory_severely_adverse\|supervisory_adverse\|exploratory\|internal` |
| `macro_variables` | `list[dict]` | Each with `variable`, `path`, `peak_shock` |
| `securities_financing_stress` | `list[str]` | Repo / sec lending stress paths |
| `desk_pl_drivers` | `list[str]` | Key P&L drivers by desk |
| `hedging_implications` | `list[str]` | Hedging strategy changes implied |
| `capital_adequacy_impacts` | `list[str]` | CET1 / leverage impacts under scenario |
| `model_update_requirements` | `list[str]` | Models requiring scenario integration |
| `submission_deadline` | `str` | ISO-8601 date or `null` |
| `action_items` | `list[str]` | |
| `confidence` | `float` | 0–1 |
| `summary` | `str` | |

---

## Filing Pipeline

In addition to skills, NaturalSentinel provides a standalone five-stage processing pipeline (`src/naturalsentinel/pipeline/`) that treats regulatory artifact processing as typed ETL rather than monolithic prompting.

```
Stage 1  ClassificationStage   → doc_type, primary_topic, complexity 1–5
Stage 2  DecompositionStage    → list[DocumentSection]  (conditional on complexity ≥ 4)
Stage 3  ExtractionStage       → dict against per-topic schema
Stage 4  ValidationStage       → type/plausibility checks + LLM correction loop
Stage 5  GroundingStage        → field → verbatim source span  (optional)
```

See `src/naturalsentinel/pipeline/stages.py` for full API. Per-topic extraction schemas: `capital`, `liquidity`, `derivatives`, `reporting`, `model_risk`, `resolution`.

```python
from naturalsentinel.pipeline import FilingPipeline

pipeline = FilingPipeline(llm, run_grounding=True)
result = pipeline.run(filing_dict)

print(result.data)                        # validated extraction
print(result.classification.primary_topic)
for g in result.grounding:
    print(f"{g.field}: '{g.source_span}'")
```

---

*Generated from `ALL_SKILLS` registry — `src/naturalsentinel/skills/__init__.py`*
