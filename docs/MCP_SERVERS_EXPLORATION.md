# MCP Server Exploration

NaturalSentinel ships its own MCP *server* (`mcp_server.py`) that exposes the
regulatory monitor to any MCP-compatible client.  This document explores the
opposite direction: running NaturalSentinel as an MCP **client** that connects
to external MCP servers to extend its capabilities.

---

## Why External MCP Servers?

| Gap in NaturalSentinel | MCP Server that fills it |
|---|---|
| Can't read local PDF archives | Filesystem MCP |
| Live fetchers cover only known APIs | Fetch MCP |
| No real-time news discovery | Brave Search MCP |
| Memory is SQLite-local, not shareable | Memory MCP (knowledge graph) |
| No access to existing compliance DBs | SQLite MCP |
| Deadline math is timezone-naive | Time MCP |

---

## Servers Explored

### 1. Filesystem MCP

**Package:** `@modelcontextprotocol/server-filesystem` (Node.js)

```bash
npx -y @modelcontextprotocol/server-filesystem /path/to/regulatory-docs
```

**Key tools:** `read_file`, `list_directory`, `search_files`

**Use case:** Compliance teams often receive regulatory guidance as PDFs on
shared drives before the official Federal Register publication.  The Filesystem
server lets an LLM read these files without a custom ingestor for each format.

**NaturalSentinel integration:** Point the server at a directory of exported
EDGAR filings or Fed supervisory letters.  The agent can then call `read_file`
mid-analysis to pull the full text of a cited exhibit.

---

### 2. Fetch MCP

**Package:** `@modelcontextprotocol/server-fetch` (Node.js)

```bash
npx -y @modelcontextprotocol/server-fetch
```

**Key tools:** `fetch`

**Use case:** NaturalSentinel's live fetchers cover the Federal Register,
BIS, and EDGAR REST APIs.  The Fetch server adds *general-purpose* URL
retrieval: an LLM can decide mid-analysis to pull a cited rulemaking page or
press release without requiring a pre-built fetcher for that agency.

**Example:**
```python
from naturalsentinel.mcp.external_servers import fetch_session, _call_tool

async with fetch_session() as session:
    result = await _call_tool(
        session,
        "fetch",
        {"url": "https://www.sec.gov/rules/proposed.shtml", "max_length": 3000},
        "fetch",
    )
    print(result.output)
```

---

### 3. Brave Search MCP

**Package:** `@modelcontextprotocol/server-brave-search` (Node.js)

```bash
export BRAVE_API_KEY=your_key
npx -y @modelcontextprotocol/server-brave-search
```

**Key tools:** `brave_web_search`, `brave_local_search`

**Use case:** Regulators sometimes publish guidance through press releases or
blog posts before the official notice.  Brave Search lets NaturalSentinel
surface breaking developments, enforcement news, and commentary on proposed
rules in real time.

**Privacy note:** Brave Search does not track users and provides independent
results — important for compliance workflows where query confidentiality matters.

---

### 4. Memory MCP (Anthropic's Knowledge-Graph Server)

**Package:** `@modelcontextprotocol/server-memory` (Node.js)

```bash
npx -y @modelcontextprotocol/server-memory
```

**Key tools:** `create_entities`, `create_relations`, `add_observations`,
`search_nodes`, `read_graph`, `delete_entities`

**Use case vs. `memory.py`:**

| | `memory.py` (built-in) | Memory MCP |
|---|---|---|
| Backend | SQLite | In-process JSON (persisted) |
| Access | NaturalSentinel only | Any MCP client |
| Memory types | Episodic / Entity / Precedent | Knowledge graph |
| Best for | Deep regulatory history | Shared entity graph across tools |

Use Memory MCP when multiple tools (Claude Desktop, Cursor, an internal
dashboard) need to read the same regulatory entity graph.  Use `memory.py`
for NaturalSentinel's richer episodic and precedent-based recall.

---

### 5. SQLite MCP

**Package:** `mcp-server-sqlite` (Python)

```bash
pip install mcp-server-sqlite
python -m mcp_server_sqlite --db-path compliance.db
```

**Key tools:** `read_query`, `write_query`, `list_tables`, `describe_table`

**Use case:** Many compliance teams already track open findings, remediation
deadlines, and business-line ownership in SQLite or similar databases.  The
SQLite server lets NaturalSentinel query live records to cross-reference new
impact assessments against existing obligations — with no ETL pipeline.

**Example query:**
```sql
SELECT domain, title, severity, deadline
FROM compliance_findings
WHERE status = 'open' AND severity IN ('high', 'critical')
ORDER BY deadline;
```

---

### 6. Time MCP

**Package:** `mcp-server-time` (Python)

```bash
pip install mcp-server-time
python -m mcp_server_time
```

**Key tools:** `get_current_time`, `convert_time`

**Use case:** Regulatory comment periods and rule-effective dates are specified
in Eastern Time (for SEC and CFPB) or UTC.  The Time server injects a reliable
"now" timestamp and timezone conversion so the LLM can accurately determine
whether a deadline has passed regardless of the server's local timezone.

---

## Claude Desktop Configuration

Add any combination of these servers to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "regulatory-monitor": {
      "command": "python",
      "args": ["/path/to/NaturalSentinel/mcp_server.py"],
      "env": { "ANTHROPIC_API_KEY": "sk-ant-..." }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/regulatory-docs"]
    },
    "fetch": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch"]
    },
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": { "BRAVE_API_KEY": "your_key" }
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    },
    "sqlite": {
      "command": "python",
      "args": ["-m", "mcp_server_sqlite", "--db-path", "/path/to/compliance.db"]
    },
    "time": {
      "command": "python",
      "args": ["-m", "mcp_server_time"]
    }
  }
}
```

---

## Running the Exploration Demo

```bash
# Install Python MCP servers
pip install 'naturalsentinel[mcp]' mcp-server-sqlite mcp-server-time

# Run all demos (Node.js servers are skipped gracefully if npx is unavailable)
python examples/explore_mcp_servers.py

# Run a single server demo
python examples/explore_mcp_servers.py --server sqlite

# Print the server registry
python examples/explore_mcp_servers.py --list
```

The demo code lives in:
- `examples/explore_mcp_servers.py` — runnable demo entry point
- `src/naturalsentinel/mcp/external_servers.py` — async context managers and tool-call helpers for each server

---

## Transport Comparison

All servers above use **stdio transport** (subprocess + stdin/stdout), which
is the most portable option.  NaturalSentinel's own server also supports:

| Transport | Flag | Best for |
|---|---|---|
| stdio | *(default)* | Local clients, Claude Desktop |
| SSE | `--transport sse` | Web clients, streaming dashboards |
| Streamable HTTP | `--transport streamable` | Production REST deployments |

See `mcp_server.py` for details on starting NaturalSentinel with alternate transports.
