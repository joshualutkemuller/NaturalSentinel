# NaturalSentinel

**Agentic regulatory change monitor with persistent memory, skill framework, and MCP server.**

Watches regulatory filings across financial services, technology, and telecom sectors — parses dense legal language using a five-stage ETL pipeline, maps changes to affected business lines, detects macro-prudential and tech regulatory regimes, and learns from human feedback over time.

```
66 tests passing · zero required dependencies · pluggable LLM backends
35 skills · 17 agents · 18 regime archetypes · 2 industry verticals
```

## Quick Start

```bash
# Clone and run — no API keys needed
cd naturalsentinel
pip install -e .
PYTHONPATH=src python examples/basic_demo.py

# Run the test suite
PYTHONPATH=src python -m unittest tests.test_all -v

# With a real LLM provider
pip install anthropic
ANTHROPIC_API_KEY=sk-ant-... PYTHONPATH=src python -m naturalsentinel.cli --provider anthropic
```

## What's New

### Five-Stage Filing Pipeline

Regulatory filings are processed through a typed ETL pipeline rather than a single monolithic prompt:

```
Classification → Decomposition → Extraction → Validation → Span Grounding
```

Each stage is independently testable and cacheable:

| Stage | Purpose | Temperature |
|-------|---------|-------------|
| **Classification** | Topic, agency, complexity scoring | 0.0 |
| **Decomposition** | Split complex documents into sections (conditional) | 0.0 |
| **Extraction** | Schema-imposed structured data pull per topic | 0.1 |
| **Validation** | Cross-field type/plausibility checks + LLM correction loop | 0.0 |
| **Span Grounding** | Map each extracted value back to verbatim source span | 0.0 |

```python
from naturalsentinel.pipeline import FilingPipeline

pipeline = FilingPipeline(llm_provider, run_grounding=True)
result = pipeline.run(filing_dict)

print(result.data)                    # validated extraction
print(result.classification.primary_topic)
for g in result.grounding:
    print(g.field, "→", g.source_span)
```

### Regime Detection

`regime_detection` identifies which macro-prudential and technology regulatory regimes are **consistent with the language observed in current filings** — it informs rather than prescribes.

Detection is two-pass: fast keyword scoring (zero LLM cost) followed by optional LLM synthesis for phase labelling and transition detection. Covers **18 regime archetypes** across financial services and technology/telecom sectors.

```python
from naturalsentinel.skills import RegimeDetectionSkill

# Via the skill framework
result = runtime.execute_skill("regime_detection", {
    "window_days": 90,
    "signal_threshold": 0.10,
})
# → active_regimes, dormant_regimes, regime_transitions, summary
```

See [`docs/REGIME_ARCHETYPES.md`](docs/REGIME_ARCHETYPES.md) for the full taxonomy.

### Skill Framework (35 Skills)

Skills are composable, permission-gated capabilities with typed inputs/outputs:

**Core Pipeline (9):** `fetch_filings`, `analyze_filing`, `recall_memory`, `store_memory`, `record_feedback`, `build_context`, `detect_duplicates`, `generate_briefing`, `scan_cycle`

**Intelligence / Analytics (6):** `alert_threshold`, `compliance_deadline`, `trend_analysis`, `cross_domain_correlation`, `export_report`, `regime_detection`

**Financial / Desk Specialist (10):** `capital_impact`, `model_risk_assessment`, `securities_financing_analysis`, `liquidity_ratio_analysis`, `agency_mortgage_analysis`, `counterparty_risk_analysis`, `regulatory_reporting_analysis`, `optimization_constraint`, `leveraged_lending_assessment`, `stress_testing_signal`

**Platform / Digital Regulatory (5):** `platform_antitrust_impact`, `data_privacy_obligation`, `ai_regulatory_impact`, `spectrum_licensing_change`, `content_moderation_liability`

**Technology / Telecom Security (5):** `cybersecurity_compliance`, `telecom_infrastructure_security`, `data_residency_obligation`, `tech_merger_review`, `algorithmic_accountability`

See [`docs/SKILLS.md`](docs/SKILLS.md) for the full catalogue.

### Agent Library (17 Agents)

Agents are thin orchestrators that compose skill invocations into high-level workflows without bypassing the permission model.

**Financial / Regulatory (12):** `ComplianceTrackerAgent`, `AlertAgent`, `CapitalOptimizationAgent`, `ModelRiskAgent`, `SecuritiesFinancingAgent`, `LiquidityRatioAgent`, `AgencyMortgageAgent`, `CounterpartyRiskAgent`, `RegulatoryReportingAgent`, `OptimizationConstraintAgent`, `LeveragedLendingAgent`, `StressTestingAgent`

**Technology / Telecom (5):** `PlatformComplianceAgent`, `DataPrivacyAgent`, `AIGovernanceAgent`, `TelecomSpectrumAgent`, `CybersecurityAgent`

## Repo Structure

```
naturalsentinel/
├── pyproject.toml
├── docs/
│   ├── SKILLS.md                    # Full skill catalogue (35 skills)
│   └── REGIME_ARCHETYPES.md         # 18-archetype regime reference card
├── src/
│   └── naturalsentinel/
│       ├── __init__.py              # Public API
│       ├── models.py                # Filing, Impact, Severity, ChangeType
│       ├── agent.py                 # Core orchestrator
│       ├── agent_framework.py       # Skill, SkillMetadata, Permission, LatencyClass
│       ├── prompts.py               # LLM prompt templates
│       ├── cli.py                   # CLI + provider factory
│       ├── providers/
│       │   ├── base.py              # ModelProvider ABC
│       │   ├── mock.py              # Zero-dep deterministic mock
│       │   ├── anthropic.py         # Claude
│       │   ├── openai.py            # GPT-4o
│       │   ├── gemini.py            # Gemini
│       │   └── ollama.py            # Local models
│       ├── fetchers/
│       │   ├── base.py              # fetch_filings + domain mappings
│       │   └── sample_data.py       # Curated filings + mock analyses
│       ├── memory/
│       │   ├── types.py             # MemoryRecord, MemoryType
│       │   ├── schema.py            # SQLite DDL
│       │   ├── similarity.py        # TF-IDF / keyword search engine
│       │   └── store.py             # MemoryStore (episodic, entity, precedent)
│       ├── pipeline/
│       │   ├── __init__.py          # Pipeline public API
│       │   └── stages.py            # 5-stage ETL pipeline
│       ├── skills/
│       │   ├── __init__.py          # ALL_SKILLS registry (35 skills)
│       │   ├── regime_detection.py  # 18 regime archetypes + detection skill
│       │   ├── capital_impact.py    # RWA / SLR / output floor
│       │   ├── ...                  # (30 additional skill modules)
│       ├── agents/
│       │   ├── __init__.py          # All 17 agents
│       │   ├── compliance_tracker.py
│       │   ├── platform_compliance_agent.py
│       │   ├── cybersecurity_agent.py
│       │   └── ...                  # (14 additional agent modules)
│       ├── mcp/
│       │   └── server.py            # MCP tools, resources, prompts
│       └── utils/
│           ├── parsing.py           # LLM JSON extraction
│           ├── serialization.py     # Enum-safe serialization
│           └── text.py              # Tokenization, similarity
├── tests/
│   ├── conftest.py                  # Shared fixtures
│   ├── test_all.py                  # 66 unittest.TestCase tests
│   └── ...                          # Additional pytest-style test modules
└── examples/
    ├── basic_demo.py                # Simplest usage
    └── memory_feedback_demo.py      # Full learning loop
```

## Architecture

```
MCP Clients (Claude Desktop, Claude Code, Cursor, custom agents)
        │
        ▼  MCP Protocol (stdio / SSE / HTTP)
┌─────────────────────────────────────────┐
│  mcp/server.py                          │
│  6 Tools · 5 Resources · 3 Prompts      │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  Agent Framework                        │
│  AgentRuntime → skill dispatch          │
│  SecurityPolicy → permission gating     │
│                                         │
│  17 Agents  ──►  35 Skills              │
│  (orchestrators)  (atomic capabilities) │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  Five-Stage Filing Pipeline             │
│  Classify → Decompose → Extract         │
│          → Validate → Ground            │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  memory/store.py                        │
│                                         │
│  Episodic    Entity       Precedent     │
│  (past       (regulation  (human        │
│   analyses)   graph)       corrections) │
│                                         │
│  SQLite + TF-IDF / keyword search       │
└─────────────────────────────────────────┘
```

## Regime Detection

18 archetypes across two verticals — each identified by keyword scoring + LLM synthesis:

**Financial Services (10):** Prudential Capital Tightening · Supervisory Scrutiny · Liquidity Stress Response · Derivatives & Margin Reform · Climate/ESG Integration · Digital Asset Capture · Resolution/TLAC Tightening · FRTB/Market Risk · Agency/GSE Reform · Consumer/Fair Lending

**Technology & Telecom (8):** Platform Antitrust Enforcement · Data Privacy Expansion · AI Governance · Cybersecurity Mandates · Spectrum Policy Reform · Content Moderation Liability · Telecom Infrastructure Security · Data Residency/Localisation

## Memory System

Three memory types make the agent improve over time:

**Episodic** — Every filing analysis is stored. When a new SEC filing arrives, the agent recalls past SEC analyses as context so it can identify patterns and maintain consistency.

**Entity graph** — Relationships are auto-extracted: "Regulation S-K → impacts → Public Equities." Over time this builds a knowledge graph of regulatory interconnections used to find non-obvious impacts.

**Precedent** — Human corrections are stored and injected into future prompts. When you say "that severity should have been critical," future analyses in the same domain see that correction as context.

```python
from naturalsentinel import MemoryStore

mem = MemoryStore("naturalsentinel.db")

# Record a correction
mem.record_feedback("SEC-2026-0312-A", "severity", "high", "critical",
                    "SEC climate rules carry real enforcement teeth")

# Recall relevant memories
results = mem.recall("climate disclosure requirements", top_k=3)

# Build context block for LLM injection
context = mem.build_context_block("sec", "new cybersecurity reporting rule")
```

## MCP Server

Exposes the agent as a standardized MCP server:

| MCP Primitive | Count | Examples |
|---|---|---|
| Tools | 6 | `scan_regulatory_filings`, `recall_memory`, `provide_feedback` |
| Resources | 5 | `naturalsentinel://filings/recent`, `naturalsentinel://entity/{name}` |
| Prompts | 3 | `regulatory_briefing`, `impact_deep_dive`, `compliance_gap_analysis` |

```bash
# Claude Desktop (stdio)
python -m naturalsentinel.mcp.server

# Web clients (SSE)
python -m naturalsentinel.mcp.server --transport sse

# Without MCP SDK
python -m naturalsentinel.mcp.server --transport standalone
```

Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "regulatory-monitor": {
      "command": "python",
      "args": ["-m", "naturalsentinel.mcp.server"],
      "env": {
        "PYTHONPATH": "/path/to/naturalsentinel/src",
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "SENTINEL_MEMORY_DB": "/path/to/naturalsentinel.db"
      }
    }
  }
}
```

## Swapping Providers

```python
from naturalsentinel import RegulatoryMonitorAgent, MemoryStore
from naturalsentinel.providers.anthropic import AnthropicProvider
from naturalsentinel.providers.openai import OpenAIProvider
from naturalsentinel.providers.ollama import OllamaProvider

memory = MemoryStore("shared.db")  # All providers share the same memory

agent = RegulatoryMonitorAgent(AnthropicProvider(), memory=memory)
agent = RegulatoryMonitorAgent(OpenAIProvider("gpt-4o"), memory=memory)
agent = RegulatoryMonitorAgent(OllamaProvider("llama3.1"), memory=memory)
```

## Dependencies

**Core: zero.** Everything runs on stdlib Python 3.11+.

Optional extras:

| Extra | Packages | Purpose |
|---|---|---|
| `anthropic` | `anthropic` | Claude provider |
| `openai` | `openai` | GPT-4o provider |
| `gemini` | `google-genai` | Gemini provider |
| `mcp` | `mcp`, `uvicorn`, `starlette` | Full MCP server |
| `search` | `scikit-learn` | TF-IDF semantic search |
| `dev` | `pytest`, `pytest-cov`, `ruff` | Development tools |

## Testing

```bash
# unittest (always works, no deps)
PYTHONPATH=src python -m unittest tests.test_all -v

# pytest (if installed)
PYTHONPATH=src python -m pytest tests/ -v

# With coverage
PYTHONPATH=src python -m pytest tests/ --cov=naturalsentinel --cov-report=term-missing
```
