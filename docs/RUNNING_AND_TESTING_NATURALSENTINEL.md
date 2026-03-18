# Running and Testing NaturalSentinel

This guide shows how to run NaturalSentinel in practice and how to test both:

1. the **legacy agentic monitoring workflow** (`RegulatoryMonitorAgent`), and
2. the newer **skill-based framework** (`AgentRuntime` + registered skills + agents).

The goal is to give you a concrete way to validate the system end to end before making deeper architectural changes.

---

## 1. Install and set up the project

From the repository root:

```bash
pip install -e .
export PYTHONPATH=src
```

Why:

- `pip install -e .` installs the package in editable mode.
- `PYTHONPATH=src` ensures the local package resolves consistently for scripts and tests.

---

## 2. Fastest way to see NaturalSentinel working

### Option A — Run the basic demo

This is the simplest proof that the core monitoring loop works with no API keys.

```bash
PYTHONPATH=src python examples/basic_demo.py
```

What it exercises:

- `RegulatoryMonitorAgent`
- `MockProvider`
- in-memory `MemoryStore`
- fetch → analyze → store workflow over sample filings

What you should expect:

- a printed summary of analyzed filings
- severity labels
- deadlines where present
- memory statistics at the end

---

### Option B — Run the CLI

This is the most production-like way to run the legacy monitor.

```bash
PYTHONPATH=src python -m naturalsentinel.cli --provider mock --reset --days 90
```

You can also persist output and memory:

```bash
PYTHONPATH=src python -m naturalsentinel.cli \
  --provider mock \
  --reset \
  --days 90 \
  --memory-db /tmp/naturalsentinel.db \
  --output /tmp/naturalsentinel-output.json
```

This is useful when you want to inspect:

- the structured JSON output,
- whether state reset works,
- whether memory accumulation changes future runs.

---

## 2B. Analyze your own local documents from the CLI

You can now point the CLI directly at local files or directories instead of only running the sample fetched workflow.

### Analyze one local file

```bash
PYTHONPATH=src python -m naturalsentinel.cli   --provider mock   --input-path /path/to/filing.txt   --input-domain sec
```

### Analyze a whole directory of documents

```bash
PYTHONPATH=src python -m naturalsentinel.cli   --provider mock   --input-dir /path/to/regulatory_docs   --input-domain fed   --output /tmp/local-analysis.json
```

### Mix files and directories

```bash
PYTHONPATH=src python -m naturalsentinel.cli   --provider mock   --input-path ./docs/sample_notice.txt   --input-path ./incoming_filings   --input-domain cftc
```

Supported local formats are currently:

- `.txt`
- `.md`
- `.rst`
- `.log`
- `.text`
- `.json`
- `.html`
- `.htm`

This is the cleanest current path if you want a lightweight operator interface for loading documents, passing paths, and getting structured JSON back without building a separate UI first.

---

## 2C. Run the Streamlit front end

If you want a cleaner front end for uploading files and reviewing results, use the included Streamlit app.

Install the UI dependency:

```bash
pip install '.[ui]'
```

Then run:

```bash
PYTHONPATH=src streamlit run streamlit_app.py
```

What the app gives you:

- multi-file upload
- domain selection
- provider/model selection
- structured impact review
- raw text preview
- downloadable JSON output

This is the cleanest current **front end** for reviewing uploaded documents without building a larger web application first.

---

## 2D. Run the styled LangChain CLI shell

If you want a terminal interface that looks and feels more like an interactive agent shell, use the Rich-formatted chat CLI.

Install the CLI extras:

```bash
pip install '.[cli]'
```

Then launch:

```bash
PYTHONPATH=src naturalsentinel-chat --provider mock --domain sec
```

Or with a LangChain-backed provider:

```bash
PYTHONPATH=src naturalsentinel-chat --provider anthropic --domain fed
PYTHONPATH=src naturalsentinel-chat --provider openai --domain sec
```

Built-in shell commands:

- `/attach <path>` — attach a file for the next message
- `/dir <path>` — approve a directory
- `/dirs` — list approved directories
- `/tools` — list available tools
- `/clear` — clear history and attachments
- `/help` — show command help
- `/exit` — quit

This shell is designed to mirror the formatting style of a modern agent CLI: boxed header, slash commands, “Thinking...” state, and conversational responses grounded in local document analyses when attachments are present.

---

## 3. Test the memory + feedback learning loop

To verify that the system is not just analyzing filings once, but can accumulate institutional memory:

```bash
PYTHONPATH=src python examples/memory_feedback_demo.py
```

What it exercises:

- first scan and episodic storage
- human feedback recording
- precedent creation
- semantic recall
- memory context assembly
- entity relation graph exploration

This is the best demo if you want to test whether the system behaves like a learning decision-support tool rather than just a one-shot parser.

---

## 4. Test the agentic framework and higher-level agents

The best walkthrough for the **framework** itself is the advanced demo:

```bash
PYTHONPATH=src python examples/advanced_agents_demo.py
```

What it exercises:

- `AgentRuntime`
- skill registration from `ALL_SKILLS`
- `scan_cycle`
- `AlertAgent`
- `ComplianceTrackerAgent`
- trend analysis
- cross-domain correlation
- report export
- audit summary of skill invocations

This is the best command to answer:

> “Is the newer skill-based agentic framework actually working end to end?”

Because it primes memory, runs multiple skills, and shows framework-level orchestration instead of only the legacy monitor.

---

## 5. Test the framework directly from Python

If you want a minimal direct framework smoke test without relying on the example scripts:

```bash
PYTHONPATH=src python - <<'PY'
from naturalsentinel import AgentRuntime, MockProvider, MemoryStore
from naturalsentinel.skills import ALL_SKILLS

runtime = AgentRuntime(
    provider=MockProvider(),
    memory=MemoryStore(":memory:"),
    state_path="/tmp/naturalsentinel_runtime_state.json",
)
runtime.register_skills(*ALL_SKILLS)

result = runtime.execute_skill("scan_cycle", {"since_days": 90})
print("success:", result.success)
print("keys:", sorted(result.data.keys()) if result.success else result.error)
print("audit:", runtime.audit.summary())

runtime.memory.close()
PY
```

This is useful when you want a compact framework validation that can later be wrapped in CI or a notebook.

---

## 6. Run the automated test suites

### Main stdlib suite

```bash
PYTHONPATH=src python -m unittest tests.test_all -v
```

This is the repository’s broad regression suite.

### Framework-focused suite

```bash
PYTHONPATH=src python -m unittest tests.test_framework -v
```

Use this when you specifically want to validate:

- permissions
- skill registry
- runtime execution
- dependency graph integrity
- skill-level behavior

### Additional targeted suites

```bash
PYTHONPATH=src python -m unittest tests.test_agent -v
PYTHONPATH=src python -m unittest tests.test_memory -v
PYTHONPATH=src python -m unittest tests.test_mcp -v
```

Use these when debugging one subsystem at a time.

---

## 7. Recommended practical validation sequence

If I were testing this repo as a user or reviewer, I would do it in this order:

### Pass 1 — “Does it run at all?”

```bash
PYTHONPATH=src python examples/basic_demo.py
```

### Pass 2 — “Does memory and feedback work?”

```bash
PYTHONPATH=src python examples/memory_feedback_demo.py
```

### Pass 3 — “Does the agentic framework orchestrate skills properly?”

```bash
PYTHONPATH=src python examples/advanced_agents_demo.py
```

### Pass 4 — “Do automated tests still pass?”

```bash
PYTHONPATH=src python -m unittest tests.test_framework -v
PYTHONPATH=src python -m unittest tests.test_all -v
```

This sequence gives you:

- demo-level confidence,
- memory-loop confidence,
- framework-level confidence,
- regression confidence.

---

## 8. Running with a real LLM provider

If you want to replace the deterministic mock provider with a real model backend, install the optional dependency for the provider you want.

### Anthropic

```bash
pip install anthropic
ANTHROPIC_API_KEY=your_key PYTHONPATH=src python -m naturalsentinel.cli --provider anthropic --days 30
```

### OpenAI

```bash
pip install openai
OPENAI_API_KEY=your_key PYTHONPATH=src python -m naturalsentinel.cli --provider openai --days 30
```

### Gemini

```bash
pip install google-genai
GEMINI_API_KEY=your_key PYTHONPATH=src python -m naturalsentinel.cli --provider gemini --days 30
```

### Ollama

```bash
PYTHONPATH=src python -m naturalsentinel.cli --provider ollama --model llama3.1 --days 30
```

For initial validation, I strongly recommend starting with `mock`, because it removes API variability and makes the workflow easier to test deterministically.

---

## 9. Testing the MCP server path

If you want to test the MCP integration path, first install the optional MCP dependencies.

```bash
pip install '.[mcp]'
PYTHONPATH=src python -m naturalsentinel.mcp.server
```

You can also run the standalone top-level server entrypoint:

```bash
PYTHONPATH=src python mcp_server.py
```

This path is most useful once you want to connect NaturalSentinel to an MCP client such as Claude Desktop or another MCP-capable tool.

---

## 10. What each path is validating

### Legacy monitor path

Use this if you want to validate:

- filing ingestion
- structured impact assessment
- dedup/state behavior
- memory persistence from the monitor loop

Best commands:

```bash
PYTHONPATH=src python examples/basic_demo.py
PYTHONPATH=src python -m naturalsentinel.cli --provider mock --reset --days 90
```

### Skill framework path

Use this if you want to validate:

- runtime orchestration
- permission-gated skill execution
- skill composition
- audit logging
- agent wrappers over skills

Best commands:

```bash
PYTHONPATH=src python examples/advanced_agents_demo.py
PYTHONPATH=src python -m unittest tests.test_framework -v
```

### Learning / feedback path

Use this if you want to validate:

- precedent capture
- semantic recall
- context injection
- entity relations

Best commands:

```bash
PYTHONPATH=src python examples/memory_feedback_demo.py
PYTHONPATH=src python -m unittest tests.test_memory -v
```

---

## 11. A good professional demo flow

If you wanted to demonstrate NaturalSentinel to a teammate, manager, or reviewer, I would use this sequence:

1. Run `examples/basic_demo.py` to show the core monitor.
2. Run `examples/memory_feedback_demo.py` to show that the system learns.
3. Run `examples/advanced_agents_demo.py` to show the skill-based framework and audit summary.
4. Run `tests.test_framework` to show that the agentic framework is programmatically testable.

That sequence tells a much stronger story than starting with isolated unit tests alone.

---

## 12. One important note on current test expectations

At the time of writing, the broad `tests.test_all` suite may expose expectation drift if the domain list and sample filings have expanded faster than some hard-coded test assertions.

So the most informative practical checks right now are:

1. `examples/basic_demo.py`
2. `examples/memory_feedback_demo.py`
3. `examples/advanced_agents_demo.py`
4. `tests.test_framework`

Those are the best places to validate the agentic workflow and framework behavior while broader regression expectations are being reconciled.
