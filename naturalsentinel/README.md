# NaturalSentinel

**Agentic regulatory change monitor with persistent memory and MCP server.**

Watches regulatory filings across SEC, CFPB, Fed, FDA, EPA, and USTR — parses dense legal language, maps changes to affected business lines, and learns from human feedback over time.

```
66 tests passing · zero required dependencies · pluggable LLM backends
```

## Quick Start

```bash
# Clone and run — no API keys needed
cd naturalsentinel
PYTHONPATH=src python examples/basic_demo.py

# Run the test suite
PYTHONPATH=src python -m unittest tests.test_all -v

# With a real LLM provider
pip install anthropic
ANTHROPIC_API_KEY=sk-ant-... PYTHONPATH=src python -m naturalsentinel.cli --provider anthropic
```

## Repo Structure

```
naturalsentinel/
├── pyproject.toml
├── run_tests.py
├── src/
│   └── naturalsentinel/
│       ├── __init__.py              # Public API
│       ├── models.py                # Filing, Impact, Severity, ChangeType
│       ├── agent.py                 # Core orchestrator
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
│       │   └── sample_data.py       # 6 curated filings + mock analyses
│       ├── memory/
│       │   ├── types.py             # MemoryRecord, MemoryType
│       │   ├── schema.py            # SQLite DDL
│       │   ├── similarity.py        # TF-IDF / keyword search engine
│       │   └── store.py             # MemoryStore (episodic, entity, precedent)
│       ├── mcp/
│       │   └── server.py            # MCP tools, resources, prompts
│       └── utils/
│           ├── parsing.py           # LLM JSON extraction
│           ├── serialization.py     # Enum-safe serialization
│           └── text.py              # Tokenization, similarity
├── tests/
│   ├── conftest.py                  # Shared fixtures
│   ├── test_all.py                  # 66 unittest.TestCase tests
│   ├── test_models.py               # pytest-style: domain types
│   ├── test_utils.py                # pytest-style: parsing, text, serialization
│   ├── test_agent.py                # pytest-style: agent pipeline
│   ├── test_memory.py               # pytest-style: memory store
│   ├── test_mcp.py                  # pytest-style: MCP standalone server
│   ├── test_providers.py            # pytest-style: provider factory
│   └── test_fetchers.py             # pytest-style: filing retrieval
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
│  agent.py                               │
│  Fetch → Deduplicate → Analyze → Store  │
│                                         │
│  providers/                             │
│  Anthropic · OpenAI · Gemini · Ollama   │
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
