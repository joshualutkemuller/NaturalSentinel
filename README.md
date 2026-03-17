# Regulatory Change Monitor & Impact Mapper

An agentic system with **persistent memory** and **MCP server** capabilities for monitoring regulatory filings across SEC, CFPB, Fed, FDA, EPA, and USTR.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP CLIENTS                              │
│   Claude Desktop  ·  Claude Code  ·  Cursor  ·  Custom Agents  │
└──────────────────────────┬──────────────────────────────────────┘
                           │  MCP Protocol (stdio / SSE / HTTP)
┌──────────────────────────▼──────────────────────────────────────┐
│                     mcp_server.py                                │
│  ┌─────────┐  ┌───────────┐  ┌──────────┐  ┌────────────────┐  │
│  │  Tools  │  │ Resources │  │ Prompts  │  │  Standalone    │  │
│  │ 6 tools │  │ 3+templates│ │ 3 prompts│  │  (no SDK)      │  │
│  └────┬────┘  └─────┬─────┘  └────┬─────┘  └───────┬────────┘  │
└───────┼─────────────┼─────────────┼─────────────────┼───────────┘
        │             │             │                 │
┌───────▼─────────────▼─────────────▼─────────────────▼───────────┐
│                       agent.py                                   │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────┐  │
│  │  Fetch       │→ │  Analyze      │→ │  Return Structured   │  │
│  │  Filings     │  │  (LLM + Mem)  │  │  Impact Assessments  │  │
│  └──────────────┘  └───────┬───────┘  └──────────────────────┘  │
│                            │                                     │
│  ┌─────────────────────────▼─────────────────────────────────┐  │
│  │              Model Provider Abstraction                     │  │
│  │  Anthropic  ·  OpenAI  ·  Gemini  ·  Ollama (local)       │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────┬────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│                       memory.py                                   │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │  Episodic   │  │   Entity     │  │     Precedent          │  │
│  │  Memory     │  │   Memory     │  │     Memory             │  │
│  │             │  │              │  │                        │  │
│  │  Full past  │  │  Regulation  │  │  Human corrections     │  │
│  │  analyses   │  │  & business  │  │  that teach the agent  │  │
│  │  for recall │  │  line graph  │  │  to self-correct       │  │
│  └──────┬──────┘  └──────┬───────┘  └────────────┬───────────┘  │
│         │                │                        │              │
│  ┌──────▼────────────────▼────────────────────────▼───────────┐  │
│  │                 SQLite + TF-IDF Search                      │  │
│  │          (falls back to keyword if no sklearn)              │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose |
|---|---|
| `agent.py` | Core agent: model providers, filing fetchers, analysis loop |
| `memory.py` | Persistent memory: SQLite store, semantic search, entity graph |
| `mcp_server.py` | MCP server: tools, resources, prompts, standalone fallback |
| `demo.py` | Basic demo with mock provider (no API keys needed) |
| `demo_memory_mcp.py` | Full demo exercising memory + MCP pipeline |

## Quick Start

```bash
# No dependencies needed for the demo
python demo_memory_mcp.py

# With a real provider
pip install anthropic
ANTHROPIC_API_KEY=sk-ant-... python agent.py --provider anthropic --days 30
```

## How Persistent Memory Works

The memory system gives the agent three capabilities that improve over time:

### 1. Episodic Memory
Every filing + analysis is stored. When a new SEC filing arrives, the agent automatically recalls past SEC analyses and includes them as context. This means the agent can say "this is similar to the climate disclosure rule from last quarter, which we rated as critical."

### 2. Entity Knowledge Graph
The agent automatically extracts relationships: "Regulation S-K → affects → Public Equities", "CFPB guidance → modifies → ECOA". Over time this builds a rich graph of regulatory interconnections. When analyzing a new filing, the agent can traverse this graph to find non-obvious impacts.

### 3. Precedent (Feedback) Memory
When a human corrects the agent — "that should have been severity=critical, not high" — the correction is stored as a precedent. Future analyses in the same domain receive these precedents as context, so the agent learns from its mistakes. This is the mechanism that makes the agent genuinely improve with use.

### Memory Context Injection

Before each LLM call, the agent builds a context block from memory:

```
--- AGENT MEMORY CONTEXT ---
RELEVANT PAST ANALYSES:
- [SEC-2026-0312-A] Climate Disclosures → severity=critical, lines=Public Equities,ESG...

CORRECTION PRECEDENTS (learn from these):
- Correction on FED-2026-0305-C.severity: high → critical (reason: $500M crypto custody exposure)

KNOWN ENTITIES:
- Regulation S-K: {"type": "regulation", "agency": "SEC", ...}
--- END MEMORY CONTEXT ---
```

This block is appended to the user prompt so the LLM sees it alongside the filing text.

## How MCP Works

The MCP server exposes the agent's capabilities as a standardized protocol that any MCP client can consume.

### Tools (things the LLM can call)

| Tool | Description |
|---|---|
| `scan_regulatory_filings` | Run a full monitoring cycle across specified agencies |
| `analyze_filing_text` | Analyze user-provided regulatory text |
| `recall_memory` | Semantic search across the agent's memory |
| `provide_feedback` | Record corrections that improve future analyses |
| `get_entity_relations` | Explore the knowledge graph |
| `get_memory_stats` | View memory system statistics |

### Resources (read-only context)

| URI | Description |
|---|---|
| `regmon://filings/recent` | Latest filing analyses |
| `regmon://memory/stats` | Memory system statistics |
| `regmon://config/domains` | Monitored domains and business lines |
| `regmon://filings/domain/{domain}` | Filing history by agency |
| `regmon://entity/{name}` | Entity knowledge and relations |

### Prompts (pre-built workflows)

| Prompt | Description |
|---|---|
| `regulatory_briefing` | Executive briefing for board/compliance/risk |
| `impact_deep_dive` | Deep analysis of a specific filing |
| `compliance_gap_analysis` | Gap analysis for a business line |

### Running the MCP Server

```bash
# For Claude Desktop (stdio transport)
python mcp_server.py

# For web clients (SSE transport)
python mcp_server.py --transport sse

# Without MCP SDK (standalone JSON-RPC over stdin/stdout)
python mcp_server.py --transport standalone
```

### Claude Desktop Configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "regulatory-monitor": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "REGMON_PROVIDER": "anthropic",
        "REGMON_MEMORY_DB": "/path/to/regmon_memory.db"
      }
    }
  }
}
```

## Swapping Model Providers

```python
from agent import RegulatoryMonitorAgent, AnthropicProvider, OpenAIProvider, OllamaProvider
from memory import MemoryStore

memory = MemoryStore("my_memory.db")

# Anthropic
agent = RegulatoryMonitorAgent(AnthropicProvider("claude-sonnet-4-20250514"), memory=memory)

# OpenAI
agent = RegulatoryMonitorAgent(OpenAIProvider("gpt-4o"), memory=memory)

# Local via Ollama
agent = RegulatoryMonitorAgent(OllamaProvider("llama3.1"), memory=memory)
```

All providers share the same memory store, so you can switch models while retaining all learned context.

## Dependencies

**Zero dependencies** for the demo (uses stdlib only).

For production:
- `anthropic` / `openai` / `google-genai` — for your chosen LLM provider
- `mcp` — for the full MCP server (`pip install mcp`)
- `scikit-learn` — for TF-IDF semantic search (optional, falls back to keyword matching)
