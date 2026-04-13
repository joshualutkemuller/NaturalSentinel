# OpenViking -- Engineer Onboarding Guide

> **OpenViking** is an open-source **context database** for AI agents, built by ByteDance/VolcEngine. It replaces fragmented vector DB setups with a virtual filesystem paradigm where memories, resources, and skills are organized under `viking://` URIs -- browsable, searchable, and observable.

---

## What Problem Does It Solve?

Traditional agent memory is a mess: memories live in code, resources live in vector DBs, skills are scattered, and retrieval is a black box. OpenViking unifies all of this into a single filesystem abstraction with three key innovations:

1. **Virtual filesystem** (`viking://`) -- context is organized as directories and files, not flat vector chunks
2. **Tiered context loading** (L0/L1/L2) -- abstracts, overviews, and full content loaded on demand to minimize token costs
3. **Observable retrieval** -- every search produces a traversal trajectory you can inspect and debug

---

## Architecture Overview

```
                    ┌─────────────────────────┐
                    │     Your AI Agent        │
                    │  (Claude, GPT, custom)   │
                    └────────┬────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        Python Client    HTTP Client    Rust CLI
        (embedded)       (remote)        (ov)
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │  OpenViking     │
                    │  Service Layer  │
                    ├─────────────────┤
                    │  VikingFS       │  ← virtual filesystem
                    │  (viking://)    │
                    ├─────────────────┤
                    │  AGFS           │  ← storage backend (Go)
                    │  VectorIndex    │  ← embeddings (C++)
                    │  Semantic Queue │  ← async L0/L1 generation
                    └─────────────────┘
                             │
                    ┌────────▼────────┐
                    │  LLM Providers  │
                    │  (VLM + Embed)  │
                    └─────────────────┘
```

---

## The Virtual Filesystem

All context lives under `viking://` URIs organized into three top-level scopes:

```
viking://
├── resources/           # Ingested docs, repos, URLs, files
│   └── my_project/
│       ├── docs/
│       └── src/
├── user/                # Persistent user memories
│   └── memories/
│       ├── preferences/   (writing style, coding habits)
│       ├── entities/      (people, orgs, tools)
│       └── events/        (meetings, decisions)
└── agent/               # Agent capabilities and task memory
    ├── skills/            (callable tool definitions)
    ├── instructions/      (behavioral directives)
    └── memories/
        ├── cases/         (specific problem/solution pairs)
        └── patterns/      (reusable processes)
```

You interact with it using filesystem-style operations: `ls`, `read`, `write`, `mkdir`, `rm`, `mv`, `glob`, `grep`.

---

## Tiered Context: L0 / L1 / L2

Every piece of content is automatically processed into three levels on write:

| Level | Name | Size | Purpose |
|-------|------|------|---------|
| **L0** | Abstract | ~100 tokens | One-sentence summary for quick relevance checks |
| **L1** | Overview | ~2k tokens | Core information for agent decision-making |
| **L2** | Details | Full content | Loaded on demand when the agent needs depth |

This means an agent can scan hundreds of entries at L0 cost, drill into a handful at L1, and only load full L2 content when actually needed. The README benchmarks show **83-96% reduction in input token cost** compared to traditional RAG.

---

## Retrieval: How Search Works

OpenViking provides two search modes:

### `find` -- Quick vector search
Direct embedding similarity against the vector index. Fast, simple.

### `search` -- Hierarchical retrieval (the powerful one)
Multi-stage process:
1. **Intent analysis** -- LLM parses the query into multiple retrieval conditions
2. **Directory-level vector search** -- finds the highest-scoring directory
3. **Refined search within directory** -- secondary retrieval scoped to that directory
4. **Recursive drill-down** -- repeats for subdirectories
5. **Result aggregation** -- returns the most relevant context with the full traversal path

The traversal path is returned with results so you can see exactly why each piece of context was selected.

---

## Session Management

OpenViking manages conversation sessions with automatic memory extraction:

```
Session lifecycle:
  create_session() → add_message() → ... → commit_session()
                                              │
                                    ┌─────────▼──────────┐
                                    │ Auto-extracts:     │
                                    │ - User preferences │
                                    │ - Entity mentions  │
                                    │ - Task patterns    │
                                    │ - Key decisions    │
                                    └────────────────────┘
```

On `commit_session()`, OpenViking archives the conversation, compresses it, and extracts long-term memories back into the `user/` and `agent/` scopes automatically.

---

## Quick Start (Python, Embedded Mode)

```python
import openviking as ov

client = ov.OpenViking(path="./data")
client.initialize()

# Ingest a resource
res = client.add_resource("https://github.com/your/repo", wait=True)
root_uri = res["root_uri"]

# Browse the filesystem
client.ls(root_uri)
client.tree(root_uri)

# Access tiered content
client.abstract(root_uri)   # L0 -- one sentence
client.overview(root_uri)   # L1 -- key details
client.read(root_uri)       # L2 -- full content

# Semantic search
results = client.find("authentication flow", target_uri=root_uri)
for r in results.resources:
    print(f"{r.uri} (score: {r.score:.4f})")

# Session with auto memory extraction
session = client.session()
session.add_message("user", "How does auth work in this project?")
session.add_message("assistant", "The project uses JWT tokens...")
session.commit()  # archives + extracts memories

client.close()
```

---

## Quick Start (Server + CLI Mode)

```bash
# Start the server
openviking-server

# CLI operations
ov status
ov add-resource https://github.com/your/repo --wait
ov ls viking://resources/
ov tree viking://resources/your/repo -L 2
ov find "what is the auth flow"
ov grep "JWT" --uri viking://resources/your/repo
```

---

## Configuration

Config lives at `~/.openviking/ov.conf` (set via `OPENVIKING_CONFIG_FILE` env var):

```jsonc
{
  "storage": {
    "workspace": "/path/to/openviking_workspace"
  },
  "log": {
    "level": "INFO",
    "output": "stdout"
  },
  "embedding": {
    "dense": {
      "provider": "openai",           // openai, volcengine, jina, voyage, gemini
      "model": "text-embedding-3-large",
      "dimension": 3072,
      "api_key": "<key>",
      "api_base": "https://api.openai.com/v1"
    },
    "max_concurrent": 10
  },
  "vlm": {
    "provider": "litellm",            // volcengine, openai, litellm
    "model": "claude-sonnet-4-6-20250514",
    "api_key": "<key>",
    "max_concurrent": 100
  }
}
```

### Supported Providers

**Embedding**: `openai`, `volcengine`, `jina`, `voyage`, `minimax`, `vikingdb`, `gemini`

**VLM (vision/language model for summarization)**:
- `volcengine` -- Doubao models
- `openai` -- GPT-4o, GPT-4V
- `litellm` -- unified access to Claude, DeepSeek, Gemini, Qwen, Ollama, vLLM, etc.

---

## Python Client API Reference

### Lifecycle
| Method | Description |
|--------|-------------|
| `OpenViking(path=)` | Create embedded client |
| `SyncHTTPClient(url=)` | Create HTTP client pointing at a running server |
| `initialize()` | Initialize storage and indexes |
| `close()` | Shut down cleanly |

### Filesystem Operations
| Method | Description |
|--------|-------------|
| `ls(uri)` | List directory contents |
| `tree(uri)` | Get directory tree |
| `read(uri)` | Read full content (L2) |
| `write(uri, content)` | Write/update file, re-indexes automatically |
| `mkdir(uri)` | Create directory |
| `rm(uri)` | Delete resource |
| `mv(from, to)` | Move resource |
| `stat(uri)` | Get resource metadata |
| `abstract(uri)` | Read L0 abstract |
| `overview(uri)` | Read L1 overview |
| `glob(pattern, uri)` | Match files by pattern |
| `grep(uri, pattern)` | Search file contents |

### Search
| Method | Description |
|--------|-------------|
| `find(query, target_uri=, limit=)` | Quick vector similarity search |
| `search(query, target_uri=, session=)` | Full hierarchical retrieval with intent analysis |

### Resources
| Method | Description |
|--------|-------------|
| `add_resource(path, wait=)` | Ingest URL, file, or directory |
| `add_skill(data)` | Register a skill definition |

### Sessions
| Method | Description |
|--------|-------------|
| `create_session(id=)` | Create a new session |
| `session(id=)` | Get or create a session object |
| `add_message(session_id, role, content)` | Add a message to a session |
| `commit_session(session_id)` | Archive session and extract memories |
| `get_session_context(session_id, token_budget=)` | Get assembled context within token budget |

### Relations
| Method | Description |
|--------|-------------|
| `link(from_uri, uris, reason)` | Create context links between URIs |
| `unlink(from_uri, uri)` | Remove a link |
| `relations(uri)` | List all relations for a URI |

### Import / Export
| Method | Description |
|--------|-------------|
| `export_ovpack(uri, to)` | Export to `.ovpack` archive |
| `import_ovpack(file_path, target)` | Import from `.ovpack` archive |

---

## MCP Integration

OpenViking ships with a Claude Code memory plugin (`examples/claude-code-memory-plugin/`) that exposes four MCP tools:

| Tool | Description |
|------|-------------|
| `memory_recall` | Semantic search across stored memories |
| `memory_store` | Explicitly store a new memory |
| `memory_forget` | Delete a memory |
| `memory_health` | Health check |

The plugin also installs two hooks:
- **`UserPromptSubmit`** -- auto-recalls relevant memories and injects them as system context
- **`Stop`** -- auto-captures conversation turns and extracts memories to OpenViking

---

## Content Parsing

OpenViking can ingest and parse 15+ formats out of the box:

| Category | Formats |
|----------|---------|
| Text | Markdown, plain text, HTML |
| Documents | PDF, Word (.docx), PowerPoint (.pptx), Excel (.xlsx), EPUB |
| Code | Python, JavaScript/TypeScript, Java, Go, Rust, C++, PHP (AST extraction via tree-sitter) |
| Archives | ZIP (recursive extraction) |
| Media | Audio, Video (with VLM transcription) |
| Web | URLs (auto-fetched and parsed) |

---

## Build Requirements

| Dependency | Version | Purpose |
|------------|---------|---------|
| Python | 3.10+ | Core runtime |
| Go | 1.22+ | AGFS storage backend |
| C++ compiler | GCC 9+ / Clang 11+ | Vector index extensions |
| Rust | Latest stable | CLI tool (optional) |

```bash
# Install from PyPI
pip install openviking --upgrade

# Install with bot framework
pip install "openviking[bot]"

# Install CLI
cargo install --git https://github.com/volcengine/OpenViking ov_cli
```

---

## Project Structure

```
OpenViking/
├── openviking/              # Core Python package
│   ├── sync_client.py       # Synchronous client (wraps async)
│   ├── async_client.py      # Async client (primary implementation)
│   ├── client/              # Local embedded client
│   ├── core/                # Data models, URI handling, skill loader
│   ├── storage/             # VikingFS, VikingDB, vector index, queue system
│   ├── session/             # Session management, compression, memory extraction
│   ├── message/             # Message/Part types (TextPart, ContextPart, ToolPart)
│   ├── parse/               # Content parsers (PDF, code, markdown, etc.)
│   ├── server/              # FastAPI HTTP server + routers
│   ├── service/             # Business logic layer
│   └── retrieve/            # Retrieval strategies
├── openviking_cli/          # CLI tool (Python wrapper around Rust binary)
├── bot/vikingbot/           # VikingBot agent framework
├── crates/                  # Rust CLI source
├── src/                     # C++ extensions (vector index)
├── examples/
│   ├── quick_start.py
│   ├── claude-code-memory-plugin/   # MCP plugin for Claude Code
│   ├── openclaw-plugin/
│   └── opencode-memory-plugin/
├── tests/
├── docs/
└── pyproject.toml
```

---

## Key Takeaways for NaturalSentinel Integration

1. **OpenViking is a context database, not just a vector DB** -- it manages the full lifecycle of agent context with filesystem semantics
2. **L0/L1/L2 tiering is the killer feature** -- it dramatically reduces token costs while maintaining recall quality
3. **The Python client supports both embedded and HTTP modes** -- embedded for single-process, HTTP for multi-service architectures
4. **Sessions auto-extract memories** -- no manual memory management needed; `commit_session()` handles it
5. **MCP integration exists** -- the Claude Code plugin is a reference implementation for hooking OpenViking into an agent via MCP tools + hooks
