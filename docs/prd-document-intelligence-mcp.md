# PRD: Document Intelligence MCP Server

**Product Requirements Document — NaturalSentinel Document Processing & Retrieval Platform**

Version: 1.0.0
Date: 2026-04-08
Authors: Jesse Viola
Status: Draft

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Solution Overview](#2-solution-overview)
3. [User Personas & Use Cases](#3-user-personas--use-cases)
4. [System Architecture](#4-system-architecture)
5. [Layer 1 — MCP Server Interface](#5-layer-1--mcp-server-interface)
6. [Layer 2 — Document Ingestion Pipeline](#6-layer-2--document-ingestion-pipeline)
7. [Layer 3 — Dual Storage Engine](#7-layer-3--dual-storage-engine)
8. [Layer 4 — Tiered Context Retrieval](#8-layer-4--tiered-context-retrieval)
9. [Layer 5 — Process Execution Engine](#9-layer-5--process-execution-engine)
10. [Layer 6 — Session & Memory Lifecycle](#10-layer-6--session--memory-lifecycle)
11. [Integration with Existing NaturalSentinel Stack](#11-integration-with-existing-naturalsentinel-stack)
12. [Data Models](#12-data-models)
13. [Configuration & Environment](#13-configuration--environment)
14. [Security & Compliance](#14-security--compliance)
15. [Deployment Architecture](#15-deployment-architecture)
16. [Migration & Rollout Plan](#16-migration--rollout-plan)
17. [Source-Grounded Analysis & Line-Level Citation](#17-source-grounded-analysis--line-level-citation)
18. [State-Level Regulatory Monitoring by Industry Sector](#18-state-level-regulatory-monitoring-by-industry-sector)

---

## 1. Problem Statement

### The Context Cost Crisis in Professional Document Work

Law firms, medical practices, compliance departments, and regulated enterprises work with documents that are structurally complex, interdependent, and must be processed according to strict procedural rules. These organizations are beginning to adopt AI agents (Claude, Codex, internal copilots) to assist with document review, but they hit three fundamental problems:

**Problem 1: Context window waste.** A 200-page contract or a patient's medical history loaded into an AI agent's context consumes the entire token budget. The agent has no way to know that only Section 14 (Indemnification) and Exhibit B (Fee Schedule) are relevant to the user's question. Every query pays the full token cost of the full document, regardless of what is actually needed.

**Problem 2: No structural awareness.** Vector databases chunk documents into flat text fragments. A 2,000-character chunk from a contract's "Termination for Cause" clause looks the same to a vector DB as a 2,000-character chunk from the "Definitions" section. The hierarchical structure of the document — sections, subsections, cross-references, exhibits — is destroyed on ingestion. When an agent retrieves "relevant chunks," it gets decontextualized fragments with no understanding of where they sit in the document's logical structure.

**Problem 3: No process enforcement.** Professional document work follows defined procedures. A medical records review requires checking diagnoses against treatment plans against billing codes in a specific order. A contract review requires checking termination clauses, then liability caps, then governing law, then cross-referencing against prior agreements. Today's RAG pipelines have no concept of procedural workflows — they answer one question at a time with no memory of what has already been reviewed, what remains, or what the process requires next.

### Why Existing Tools Fall Short

| Approach | Structural Awareness | Token Efficiency | Process Enforcement |
|----------|---------------------|-----------------|---------------------|
| Raw document in context | None — flat text | Terrible — full doc every query | None |
| Traditional RAG (Qdrant/Pinecone) | None — flat chunks | Better — only relevant chunks | None |
| OpenViking alone | Excellent — viking:// filesystem | Excellent — L0/L1/L2 tiering | Partial — sessions only |
| **This system** | **Excellent — OV filesystem + doc-aware parsing** | **Excellent — L0/L1/L2 + Qdrant vector precision** | **Full — process definitions with step tracking** |

### What This Unlocks

A law firm attaches a 300-page merger agreement to a Claude conversation. Instead of dumping 300 pages into context, our MCP server:

1. Parses the document into its structural hierarchy (articles, sections, schedules, exhibits)
2. Generates L0 abstracts (~100 tokens each) for every section — the agent can "scan the table of contents" for pennies
3. Indexes embeddings in Qdrant for fast semantic search across all sections
4. When the agent asks about indemnification, Qdrant finds the right sections, OpenViking serves the L1 overview (key obligations, caps, carve-outs) instead of the full 15-page section
5. Only when the agent needs the exact clause language does the full L2 text load
6. A stored process definition ("M&A Review Checklist") tracks which sections have been reviewed, flags what remains, and enforces the firm's standard review order

The same pattern applies to medical records, compliance filings, insurance claims, patent applications — any domain where documents are structured, large, and processed according to defined procedures.

---

## 2. Solution Overview

### Core Concept

An MCP server that AI agents connect to for document processing and retrieval. The server combines two storage backends — **OpenViking** for hierarchical context management and **Qdrant** for vector similarity search — to provide token-efficient, structure-aware, process-driven document intelligence.

### Design Principles

1. **Agents are the users, not humans.** The MCP server exposes tools that AI agents call. Humans interact with their agent (Claude, Codex, etc.) and the agent delegates document work to our server. This means our API surface must be agent-friendly: clear tool descriptions, structured inputs/outputs, and predictable behavior.

2. **Structure over chunks.** Documents are not bags of text. They have hierarchies, cross-references, and logical relationships. Our ingestion pipeline preserves and indexes this structure so retrieval understands document topology, not just text similarity.

3. **Pay for what you need.** The L0/L1/L2 tiering system means an agent browsing 50 documents pays ~5,000 tokens (50 x L0 abstracts), not ~500,000 tokens (50 x full documents). Depth is loaded on demand.

4. **Process is a first-class concept.** Document review procedures are stored as executable definitions. The system tracks progress, enforces step ordering, and maintains state across sessions.

5. **Dual-engine retrieval.** Qdrant handles "find me something similar to X" (vector similarity). OpenViking handles "show me the children of this section" and "give me the L1 overview of Section 14" (structural navigation). Both are needed; neither alone is sufficient.

---

## 3. User Personas & Use Cases

### Persona 1: Law Firm Associate

**Context:** Reviews 10-20 contracts per week. Each contract is 50-300 pages. The firm has a standard review checklist (28 items) that must be completed for every agreement.

**Current pain:** Copies contract into ChatGPT/Claude. Asks questions one at a time. No memory between sessions. Misses cross-references. No audit trail of what was reviewed.

**With this system:**
- Attaches contract PDF to Claude conversation
- Claude calls `ingest_document` — contract is parsed into structural hierarchy
- Claude calls `follow_process("contract_review_checklist")` — begins systematic review
- Each step retrieves only the relevant sections at L1 depth, escalating to L2 when clause-level precision is needed
- Progress is tracked. If the associate returns tomorrow, the system knows steps 1-12 are complete and resumes at step 13
- Final output: completed checklist with citations to specific clauses

### Persona 2: Medical Practice Administrator

**Context:** Manages patient records, insurance pre-authorizations, and compliance documentation. Documents include intake forms, lab results, treatment plans, referral letters, billing records.

**Current pain:** Patient context is scattered across EHR exports, PDFs, and faxed documents. When preparing for an appeal or audit, the administrator manually assembles the relevant history.

**With this system:**
- Uploads patient document bundle (intake form, labs, treatment plan, billing)
- System parses each document type with domain-aware structure recognition
- When preparing an insurance appeal, the agent calls `follow_process("insurance_appeal_preparation")`
- Process definition specifies: (1) extract diagnosis codes, (2) match against treatment plan, (3) verify billing alignment, (4) identify supporting lab results, (5) draft appeal narrative
- Each step retrieves only the relevant sections from the relevant documents, cross-referencing across the bundle

### Persona 3: Compliance Officer

**Context:** Monitors regulatory filings (already handled by NaturalSentinel's existing skills) AND must review internal policies against new regulations.

**Current pain:** When a new SEC rule drops, must manually compare it against 15 internal policy documents to identify gaps.

**With this system:**
- Internal policy documents are already ingested and indexed
- When `scan_regulatory_filings` finds a new SEC final rule, the compliance officer asks their agent to assess impact
- Agent calls `recall_context("SEC Rule 10b-5 amendments")` — retrieves the new rule AND the relevant internal policies
- Agent calls `follow_process("regulatory_gap_analysis")` — systematically compares each obligation in the new rule against existing policy coverage
- Output: gap analysis with citations to both the regulation and the internal policy

---

## 4. System Architecture

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    AI Agent (Claude, Codex, etc.)         │
│                                                          │
│  User says: "Review this contract for liability issues"  │
│  Agent decides to call MCP tools                         │
└──────────────┬───────────────────────────────────────────┘
               │
               │  MCP Protocol (stdio / streamable-http)
               │
┌──────────────▼───────────────────────────────────────────┐
│           LAYER 1: MCP Server Interface                  │
│                                                          │
│  Tools:                     Resources:                   │
│  ├── ingest_document        ├── doc://{doc_id}/structure │
│  ├── recall_context         ├── doc://{doc_id}/status    │
│  ├── follow_process         └── process://registry       │
│  ├── list_documents                                      │
│  ├── document_status        Prompts:                     │
│  └── register_process       ├── document_review          │
│                             └── process_summary          │
└──────────────┬───────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────┐
│           LAYER 2: Document Ingestion Pipeline           │
│                                                          │
│  Content Detection → Format Parser → Structure Extractor │
│  → Section Hierarchy Builder → L0/L1/L2 Generator        │
│  → Embedding Generator → Dual-Write to Storage           │
│                                                          │
│  Parsers: PDF, DOCX, HTML, Markdown, Plain Text          │
│  Structure: Legal (articles/sections/clauses),           │
│             Medical (findings/diagnoses/plans),           │
│             Generic (headings/paragraphs)                 │
└──────────────┬──────────────────────┬────────────────────┘
               │                      │
┌──────────────▼──────────┐ ┌─────────▼────────────────────┐
│  LAYER 3A: OpenViking   │ │  LAYER 3B: Qdrant            │
│  Context Database       │ │  Vector Database              │
│                         │ │                               │
│  viking://documents/    │ │  Collection: ns_documents     │
│  ├── {doc_id}/          │ │  ├── Payload: uri, doc_id,    │
│  │   ├── .abstract.md   │ │  │   section_path, level,     │
│  │   ├── .overview.md   │ │  │   doc_type, metadata       │
│  │   ├── article-1/     │ │  ├── Vector: dense embedding  │
│  │   │   ├── section-1/ │ │  │   (text-embedding-3-large) │
│  │   │   └── section-2/ │ │  └── Index: HNSW              │
│  │   └── exhibits/      │ │                               │
│  └── {doc_id_2}/        │ │  Collection: ns_processes     │
│                         │ │  (process step embeddings)    │
│  viking://processes/    │ │                               │
│  └── {process_name}/    │ │  Collection: ns_sessions      │
│                         │ │  (session memory embeddings)  │
│  viking://sessions/     │ │                               │
│  └── {session_id}/      │ │                               │
└─────────────────────────┘ └───────────────────────────────┘
               │                      │
┌──────────────▼──────────────────────▼────────────────────┐
│           LAYER 4: Tiered Context Retrieval              │
│                                                          │
│  Query → Intent Analysis → Dual-Path Retrieval:          │
│                                                          │
│  Path A (Qdrant):                                        │
│    Embed query → kNN search → score + filter → URIs      │
│                                                          │
│  Path B (OpenViking):                                    │
│    Hierarchical directory retrieval → L0 scan →          │
│    L1 expansion for top candidates → L2 on demand        │
│                                                          │
│  Merge: rank fusion → deduplicate → tiered assembly      │
│  Output: context block within token budget               │
└──────────────┬───────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────┐
│           LAYER 5: Process Execution Engine              │
│                                                          │
│  Process Definition (markdown) → Step Parser →           │
│  State Tracker → Step Executor → Result Aggregator       │
│                                                          │
│  Each step: retrieval query + validation rule +          │
│  output schema + depends_on references                   │
│                                                          │
│  State persisted in viking://sessions/{id}/progress/     │
└──────────────┬───────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────┐
│           LAYER 6: Session & Memory Lifecycle            │
│                                                          │
│  Session tracking → Message logging → Auto-commit →      │
│  Memory extraction → Precedent storage →                 │
│  Cross-document entity linking                           │
│                                                          │
│  Integrates with existing PgMemoryStore for persistent   │
│  episodic/entity/precedent memories                      │
└──────────────────────────────────────────────────────────┘
```

### Relationship to Existing NaturalSentinel Stack

This system is **additive, not replacing**. It extends the existing architecture:

| Existing Component | Role in This System |
|---|---|
| `AgentRuntime` + `SkillRegistry` | New document skills register alongside existing 35 skills. Same Permission model, same AuditLog, same SecurityPolicy. |
| `PgMemoryStore` + `PgMemory` table | Continues to store episodic/entity/precedent memories. Document analysis results become episodic memories. Entity relations link document sections to regulatory concepts. |
| `SimilarityEngine` | Replaced by Qdrant for vector search. Token-overlap scoring in `pg_store.py` becomes a fallback, not the primary path. |
| Existing MCP server (`mcp/server.py`) | Extended — state monitoring tools (`scan_state_filings`, `get_sector_regulatory_calendar`) are added here because they are monitoring operations, not document review. The document intelligence tools (`ingest_document`, `recall_context`, `follow_process`, `list_documents`, `document_status`, `register_process`) run in a **second MCP server** (`mcp/document_server.py`). Both servers share the same Qdrant and OpenViking backends via `deps.py` dependency injection. An agent that needs both capabilities connects to both servers. |
| `Settings` in `core/config.py` | Extended with Qdrant and OpenViking configuration fields. |
| `compose.yml` | Qdrant service already provisioned. OpenViking service added. |
| Fetchers (`fetchers/live/`) | Continue to fetch regulatory filings. Document ingestion is a separate pipeline for user-uploaded documents, but shares the same `html_to_text` and parsing utilities from `fetchers/live/parsers.py`. |
| Lineage (`citation.py`, `trace.py`, `provenance.py`) | Reused directly. Every document analysis produces a `DecisionTrace`, every extracted field gets a `FieldCitation`, every LLM call records `ModelProvenance`. |
| Governance (`audit.py`, `policy.py`) | Reused directly. Document processing events are audit-logged. Escalation policies apply to document analysis the same way they apply to filing analysis. |

---

## 5. Layer 1 — MCP Server Interface

### Transport

The server supports the same transports as the existing MCP server, controlled by `MCP_TRANSPORT` in `Settings`:
- `stdio` — for local agent connections (Claude Code, Codex CLI)
- `streamable-http` — for remote agent connections over HTTP

### MCP Tools

#### `ingest_document`

**Purpose:** Accept a document from the agent, parse it, build the structural hierarchy, generate L0/L1/L2 tiers, index embeddings, and store in both OpenViking and Qdrant.

**Input Schema:**
```json
{
  "source": {
    "file_path": "string — absolute local path (CLI / backend use only)",
    "url":       "string — fetch document from this URL (agent-friendly; used for regulatory filings)",
    "content":   "string — base64-encoded file content (for agent file-attachment uploads)"
  },
  "content_type": "string (optional) — MIME type hint when using 'content' source",
  "doc_type": "string (optional) — 'legal', 'medical', 'compliance', 'generic'. Auto-detected if omitted.",
  "metadata": {
    "client_name": "string (optional)",
    "matter_id": "string (optional)",
    "document_date": "string (optional, ISO format)",
    "jurisdiction": "string (optional)",
    "tags": ["string (optional)"]
  },
  "wait": "boolean (optional, default true) — block until processing completes"
}
```

Exactly one of `source.file_path`, `source.url`, or `source.content` must be provided.
`file_path` is for local/CLI use only and is rejected over remote MCP connections.
`url` is the standard path for regulatory filing ingestion — the pipeline fetches, parses,
and stores the document, making it safe for remote agents without exposing server filesystem paths.
```

**Output:**
```json
{
  "doc_id": "uuid",
  "uri": "viking://documents/{doc_id}",
  "title": "string — extracted document title",
  "doc_type": "string — detected or provided type",
  "section_count": "int — number of structural sections extracted",
  "status": "'processing' | 'ready'",
  "structure_summary": "string — L0 abstract of the entire document"
}
```

**Processing steps:**
1. Detect file format (PDF, DOCX, HTML, MD, TXT) using extension + magic bytes
2. Parse content using appropriate parser (reuse OpenViking parsers for PDF/DOCX/HTML, extend with domain-specific structure extraction)
3. Build section hierarchy tree (see Layer 2)
4. Create OpenViking directory structure under `viking://documents/{doc_id}/`
5. Generate L0 abstract and L1 overview for each section node (via VLM)
6. Generate dense embeddings for L0, L1, and L2 content of each section
7. Write embeddings to Qdrant collection `ns_documents` with payload containing uri, section_path, level, doc_type
8. Return doc_id and structure summary

#### `recall_context`

**Purpose:** Retrieve relevant document context for an agent's query, using both Qdrant vector search and OpenViking hierarchical retrieval, assembled within a token budget.

**Input Schema:**
```json
{
  "query": "string (required) — the agent's question or information need",
  "doc_ids": ["string (optional) — scope to specific documents. Empty = search all user-uploaded docs."],
  "collections": ["string (optional) — Qdrant collections to search. Default: ['ns_documents']. Include 'ns_state_filings' for regulatory content, 'ns_sessions' for past session memories."],
  "token_budget": "int (optional, default 6144) — max tokens in returned context",
  "depth": "'abstract' | 'overview' | 'detail' (optional, default 'overview') — maximum L-level to return",
  "include_cross_references": "boolean (optional, default true) — follow document cross-references"
}
```

**Collection routing:**
- `ns_documents` — user-uploaded documents (contracts, policies, medical records)
- `ns_state_filings` — ingested state regulatory filings (use for regulatory gap analysis)
- `ns_sessions` — cross-session memories extracted from prior reviews

When both `ns_documents` and `ns_state_filings` are searched (e.g., a compliance gap analysis
comparing an internal policy against a new state rule), results from both collections are merged
via rank fusion before tiered assembly.
```

**Output:**
```json
{
  "context_blocks": [
    {
      "uri": "viking://documents/{doc_id}/article-5/section-2",
      "doc_id": "uuid",
      "section_path": "Article 5 > Section 5.2 — Indemnification",
      "level": "overview",
      "content": "string — the L1 overview text",
      "relevance_score": 0.92,
      "source": "'qdrant' | 'openviking' | 'merged'"
    }
  ],
  "total_tokens": 3847,
  "retrieval_trajectory": {
    "qdrant_candidates": 12,
    "ov_candidates": 8,
    "merged_unique": 15,
    "returned": 6,
    "directories_traversed": ["viking://documents/{doc_id}/article-5/", "..."]
  }
}
```

**Retrieval flow:**
1. Embed query using the configured embedding model
2. **Qdrant path:** kNN search against `ns_documents` collection, filtered by `doc_ids` if provided. Returns top-K URIs with scores.
3. **OpenViking path:** Hierarchical retrieval using `search()` — intent analysis, directory-level positioning, recursive drill-down. Returns URIs with scores and traversal trajectory.
4. **Merge:** Reciprocal rank fusion across both result sets. Deduplicate by URI.
5. **Tier assembly:** For each result, fetch content at the requested depth (L0/L1/L2). Start with L1. If total tokens exceed budget, demote lowest-scoring results to L0. If budget remains, promote highest-scoring results to L2.
6. Return assembled context blocks with token count and retrieval trajectory.

#### `follow_process`

**Purpose:** Execute a defined document review process, step by step. Each step specifies what to retrieve, what to check, and what to output. The agent receives one step at a time and can advance, pause, or resume.

**Input Schema:**
```json
{
  "process_name": "string (required) — name of the registered process definition",
  "doc_ids": ["string (required) — documents to process against"],
  "session_id": "string (optional) — resume an existing session. Omit to start new.",
  "action": "'start' | 'next' | 'skip' | 'status' | 'complete' (optional, default 'start')",
  "step_result": {
    "findings": "string (optional) — agent's findings for the current step",
    "status": "'pass' | 'fail' | 'flagged' | 'skipped' (optional)"
  }
}
```

**Output:**
```json
{
  "session_id": "uuid",
  "process_name": "contract_review_checklist",
  "current_step": {
    "step_number": 13,
    "name": "Limitation of Liability",
    "instruction": "Review liability cap provisions. Check for: (1) aggregate cap amount or formula, (2) exclusions from cap (IP indemnity, confidentiality breach, willful misconduct), (3) consequential damages waiver, (4) mutual vs one-sided structure.",
    "retrieval_query": "limitation of liability cap consequential damages waiver exclusions",
    "context": [
      {
        "uri": "viking://documents/{doc_id}/article-8/section-8-3",
        "section_path": "Article 8 > Section 8.3 — Limitation of Liability",
        "level": "detail",
        "content": "string — full clause text (L2)"
      }
    ],
    "depends_on": [12],
    "output_schema": {
      "cap_amount": "string",
      "cap_formula": "string",
      "exclusions": ["string"],
      "consequential_waiver": "boolean",
      "mutual": "boolean",
      "concerns": ["string"]
    }
  },
  "progress": {
    "total_steps": 28,
    "completed": 12,
    "flagged": 2,
    "remaining": 16
  }
}
```

#### `list_documents`

**Purpose:** List all ingested documents with their status and metadata.

**Input Schema:**
```json
{
  "doc_type": "string (optional) — filter by type",
  "tags": ["string (optional) — filter by tags"],
  "limit": "int (optional, default 50)"
}
```

**Output:** Array of document summaries (doc_id, title, uri, doc_type, section_count, status, created_at, tags).

#### `document_status`

**Purpose:** Get detailed status of a specific document including its structural hierarchy.

**Input Schema:**
```json
{
  "doc_id": "string (required)"
}
```

**Output:** Document metadata + full section tree with L0 abstracts for each node + processing status + index stats (embedding count, Qdrant point count).

#### `register_process`

**Purpose:** Register a new process definition from a markdown file or structured definition.

**Input Schema:**
```json
{
  "name": "string (required) — unique process identifier",
  "definition": "string (required) — markdown process definition (see Layer 5 for format)",
  "doc_types": ["string (optional) — which document types this process applies to"],
  "description": "string (optional)"
}
```

**Output:** Confirmation with parsed step count and validation result.

### MCP Resources

| URI Pattern | Description |
|---|---|
| `doc://{doc_id}/structure` | Full section hierarchy with L0 abstracts |
| `doc://{doc_id}/status` | Processing status and index stats |
| `process://registry` | List of all registered process definitions |
| `process://{process_name}` | Full process definition with step details |

### MCP Prompts

| Prompt Name | Arguments | Description |
|---|---|---|
| `document_review` | `doc_id`, `focus_area` (optional) | System prompt for reviewing a specific document with focus guidance |
| `process_summary` | `session_id` | System prompt with completed process state for generating a summary report |
| `cross_reference` | `doc_ids[]` | System prompt for comparing/cross-referencing multiple documents |

---

## 6. Layer 2 — Document Ingestion Pipeline

### Pipeline Stages

```
File Input
    │
    ▼
┌─────────────────────────────┐
│ Stage 1: Format Detection   │
│                             │
│ Extension + magic bytes     │
│ → PDF, DOCX, HTML, MD, TXT │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Stage 2: Content Extraction │
│                             │
│ Reuses OpenViking parsers:  │
│ - PDFParser (pdfplumber)    │
│ - WordParser (python-docx)  │
│ - HTMLParser (custom)       │
│ - MarkdownParser            │
│ - TextParser                │
│                             │
│ Output: raw text + metadata │
│ (page numbers, headings,    │
│  formatting cues)           │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ Stage 3: Structure Extraction           │
│                                         │
│ Domain-specific structure recognizers:  │
│                                         │
│ LEGAL:                                  │
│   Regex + heading detection for:        │
│   Articles → Sections → Subsections     │
│   Schedules, Exhibits, Appendices       │
│   Recitals, Definitions, Signatures     │
│   Cross-reference detection (§, Art.)   │
│                                         │
│ MEDICAL:                                │
│   Section header recognition for:       │
│   Chief Complaint, History, Exam,       │
│   Assessment, Plan, Orders, Labs        │
│   ICD/CPT code extraction               │
│                                         │
│ COMPLIANCE:                             │
│   Obligation extraction:                │
│   "shall", "must", "required to"        │
│   Deadline extraction (date patterns)   │
│   Reference linkage (CFR, USC, FR)      │
│                                         │
│ GENERIC:                                │
│   Heading hierarchy (H1→H2→H3)         │
│   Paragraph grouping                    │
│                                         │
│ Output: DocumentTree                    │
│   (nested nodes with text + metadata)   │
└──────────┬──────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│ Stage 4: Hierarchy Builder                   │
│                                              │
│ DocumentTree → OpenViking directory structure │
│                                              │
│ Each node becomes a viking:// directory:     │
│   viking://documents/{doc_id}/               │
│   ├── article-1/                             │
│   │   ├── section-1-1/                       │
│   │   │   └── (leaf: full text as file)      │
│   │   └── section-1-2/                       │
│   ├── article-2/                             │
│   ├── schedules/                             │
│   │   ├── schedule-a/                        │
│   │   └── schedule-b/                        │
│   └── exhibits/                              │
│       └── exhibit-1/                         │
│                                              │
│ Cross-references stored as OpenViking        │
│ relations: link(from_uri, [target_uris])     │
└──────────┬───────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│ Stage 5: L0/L1/L2 Generation                │
│                                              │
│ For each node in the hierarchy:              │
│                                              │
│ L2 (Detail): Original section text           │
│   → Written to OpenViking as file content    │
│   → Stored as-is, no summarization           │
│                                              │
│ L1 (Overview): VLM-generated summary         │
│   → Prompt: "Summarize this section in       │
│     500-2000 tokens. Preserve key terms,     │
│     obligations, dates, and amounts."         │
│   → Written to .overview.md                  │
│                                              │
│ L0 (Abstract): VLM-generated one-liner       │
│   → Prompt: "One sentence describing what    │
│     this section covers and its significance" │
│   → Written to .abstract.md                  │
│                                              │
│ Async: Queued via OpenViking's               │
│   SemanticQueue / EmbeddingQueue             │
│   (configurable concurrency via              │
│    vlm.max_concurrent in ov.conf)            │
└──────────┬───────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│ Stage 6: Embedding & Dual-Write             │
│                                              │
│ For each L0, L1, L2 text:                    │
│   1. Generate dense embedding                │
│      (text-embedding-3-large, 3072 dims)     │
│                                              │
│   2. Write to OpenViking VectorDB            │
│      (internal vector index, used for        │
│       hierarchical retrieval)                │
│                                              │
│   3. Write to Qdrant                         │
│      Collection: ns_documents                │
│      Point:                                  │
│        id: deterministic UUID from viking_uri+level   │
│        vector: dense embedding                        │
│        payload:                                       │
│          viking_uri: viking://documents/...           │
│          chunk_id: "{doc_id}:{section}:{index}"       │
│          doc_id: parent document UUID                 │
│          source_url: original file URL or path        │
│          section_path: "Art 5 > § 5.2"               │
│          level: 0 | 1 | 2                             │
│          doc_type: "legal"                            │
│          node_type: "section" | "clause" ...          │
│          title: section heading                       │
│          abstract: L0 text                            │
│          excerpt: verbatim text (L2 only)             │
│          line_start/line_end: (L2 only)               │
│          created_at: ISO timestamp                    │
│          tags: from document metadata                 │
│                                              │
│ Why dual-write:                              │
│ - OpenViking vector index: used internally   │
│   for hierarchical retrieval (directory-     │
│   scoped searches, score propagation)        │
│ - Qdrant: used for fast global kNN search    │
│   with rich payload filtering (doc_type,     │
│   tags, level, date ranges)                  │
└──────────────────────────────────────────────┘
```

### Integration with Existing Parsers

The ingestion pipeline reuses two existing parser systems:

**OpenViking parsers** (`openviking/parse/parsers/`): `BaseParser` subclasses for PDF, Word, HTML, Markdown, code, etc. These handle raw content extraction — turning a PDF into text with page/heading markers. They support tree-sitter AST extraction for code files.

**NaturalSentinel parsers** (`fetchers/live/parsers.py`): `html_to_text()`, `normalise_whitespace()`, `truncate()`, `detect_change_type()`. These handle HTML cleanup and text normalization. Already tested in production with Federal Register, EDGAR, and FINRA content.

The new **structure extractors** (legal, medical, compliance, generic) are a new layer that sits between content extraction and hierarchy building. They take parsed text and produce a `DocumentTree` — a nested structure of named, typed nodes. This is the novel contribution of this system; it is what makes our retrieval structure-aware rather than chunk-based.

---

## 7. Layer 3 — Dual Storage Engine

### 3A: OpenViking — The Context Database

**Role:** Hierarchical context management, L0/L1/L2 tiering, session memory, relation tracking, and directory-scoped retrieval.

**How it runs:** Embedded Python client (`openviking.OpenViking(path=...)`) running in-process with the MCP server. No separate HTTP server needed. The AGFS storage backend writes to a local workspace directory.

**Directory Layout:**

```
viking://
├── documents/                          # All ingested documents
│   └── {doc_id}/
│       ├── .abstract.md                # L0: "Merger agreement between X and Y..."
│       ├── .overview.md                # L1: Key terms, parties, dates, obligations
│       ├── meta.json                   # Document metadata (type, source, tags)
│       ├── definitions/
│       │   ├── .abstract.md
│       │   └── .overview.md
│       ├── article-1--representations/
│       │   ├── .abstract.md
│       │   ├── .overview.md
│       │   ├── section-1-1/
│       │   └── section-1-2/
│       └── exhibits/
│           ├── exhibit-a/
│           └── exhibit-b/
│
├── processes/                          # Registered process definitions
│   └── {process_name}/
│       ├── definition.md               # Full process definition
│       ├── .abstract.md                # L0: "28-step M&A contract review..."
│       └── .overview.md                # L1: Step summary with dependencies
│
├── sessions/                           # Active and archived sessions
│   └── {session_id}/
│       ├── messages.jsonl              # Conversation log
│       ├── progress/                   # Process execution state
│       │   └── {process_name}.json     # Step completion, findings, flags
│       └── history/                    # Archived session segments
│           └── archive_001/
│
├── user/                               # User memories (existing OV scope)
│   └── memories/
│       ├── preferences/
│       ├── entities/
│       └── events/
│
└── agent/                              # Agent memories (existing OV scope)
    ├── memories/
    │   ├── cases/                      # Past review findings
    │   └── patterns/                   # Recurring document patterns
    ├── instructions/
    └── skills/
```

### OpenViking URI Namespace Policy

All paths under `viking://` follow a defined namespace convention:

| Namespace | Content | Owner |
|---|---|---|
| `viking://documents/{doc_id}/` | User-uploaded documents (contracts, policies, medical records) | Per-user (`created_by` enforced) |
| `viking://federal_regulations/{domain}/{doc_id}/` | Federal regulatory filings ingested by the fetcher pipeline | Shared (read-only for users) |
| `viking://state_regulations/{state_code}/{sector}/{doc_id}/` | State regulatory filings by state + sector | Shared (read-only for users) |
| `viking://processes/{process_name}/` | Registered process definitions | Shared (firm-wide) |
| `viking://sessions/{session_id}/` | Active/archived conversation sessions | Per-session |
| `viking://user/memories/` | User preference and entity memories | Per-user |
| `viking://agent/memories/` | Agent pattern and case memories | Shared |

This namespace convention means retrieval can be scoped by type without additional metadata filters:
`client.ls("viking://state_regulations/CA/")` lists all CA state filings.
`client.search(query, target="viking://documents/")` searches only user-uploaded docs.

**Key OpenViking operations used:**

| Operation | API Call | Purpose |
|---|---|---|
| Create doc structure | `client.mkdir(uri)` per node | Build hierarchy |
| Write L0/L1 | Handled by `add_resource()` pipeline | Auto-generates .abstract.md, .overview.md |
| Write L2 | `client.write(uri, content)` | Store full section text |
| Browse structure | `client.ls(uri)`, `client.tree(uri)` | Agent explores document |
| Read tiered content | `client.abstract(uri)`, `client.overview(uri)`, `client.read(uri)` | Retrieve at desired depth |
| Cross-references | `client.link(from_uri, [target_uris], reason)` | Track section cross-refs |
| Hierarchical search | `client.search(query, target_uri)` | Directory-scoped retrieval |
| Session management | `client.session()`, `.add_message()`, `.commit()` | Conversation tracking + memory extraction |

### 3B: Qdrant — The Vector Database

**Role:** Fast global vector similarity search with rich payload filtering. Complements OpenViking's hierarchical retrieval with flat-but-fast kNN search.

**Already provisioned** in `compose.yml` at port `6333` with persistent storage volume `qdrant-data`.

**Collections:**

#### `ns_documents` — Document section embeddings

```
Vector: 3072 dimensions (text-embedding-3-large)
Distance: Cosine
Index: HNSW (ef_construct=128, m=16)

Payload schema:
  viking_uri:           keyword    — viking:// URI for this section+level (stable pointer)
  chunk_id:             keyword    — "{doc_id}:{section_path}:{chunk_index}" (citation anchor)
  doc_id:               keyword    — parent document UUID
  source_url:           keyword    — original file URL or local path (for citation)
  section_path:         text       — human-readable path ("Article 5 > Section 5.2")
  level:                integer    — 0 (L0), 1 (L1), 2 (L2)
  doc_type:             keyword    — "legal", "medical", "compliance", "generic"
  node_type:            keyword    — "article", "section", "clause", "exhibit", etc.
  title:                text       — section heading
  abstract:             text       — L0 text (always populated, for fast L0 scanning)
  excerpt:              text       — first 200 chars of verbatim source text (L2 only)
  line_start:           integer    — 1-indexed line number in source file (L2 only)
  line_end:             integer    — (L2 only)
  char_offset_start:    integer    — byte offset in source file (L2 only)
  char_offset_end:      integer    — (L2 only)
  page_number:          integer    — PDF page number (L2 only, null for text/HTML sources)
  created_at:           datetime   — ingestion timestamp
  tags:                 keyword[]  — from document metadata
  word_count:           integer    — token estimate for budget planning
```

Citation fields (`excerpt`, `line_start`, `line_end`, `char_offset_*`, `page_number`) are populated
only for L2 points. L0 and L1 points leave these null — they are generated summaries, not
source text, and cannot be cited. Only L2 points carry verbatim source passages eligible for citation.

**Why Qdrant alongside OpenViking's internal vector index:**

OpenViking's vector index is tightly coupled to its hierarchical retrieval strategy — it searches within directory scopes, propagates scores up/down the tree, and applies hotness decay. This is excellent for "explore this document" queries but suboptimal for "find the most relevant section across all 50 documents" queries.

Qdrant provides:
- **Global search** across all documents without directory scoping overhead
- **Rich filtering** — find all L1 overviews of legal sections tagged "indemnification" across documents of type "legal" created in the last 30 days
- **Horizontal scaling** — when the corpus grows to millions of sections, Qdrant handles it without affecting OpenViking's per-document hierarchical performance
- **Separation of concerns** — OpenViking manages context lifecycle (tiering, sessions, memory); Qdrant handles pure vector math

#### `ns_sessions` — Session memory embeddings

For cross-session recall. When a session is committed and memories are extracted, those memories are also embedded and stored in Qdrant for fast retrieval in future sessions.

```
Payload: session_id, memory_type, category, extracted_at, summary
```

### Relationship to Existing Memory Infrastructure

The existing `PgMemoryStore` and `PgMemory` table in PostgreSQL continue to serve as the **relational memory store** — structured records of episodic memories, entity relations, feedback logs, belief states, audit events, decision traces, and citations.

Qdrant becomes the **vector index layer** that the current codebase has been designed for but never wired up. The placeholder comment in `pg_store.py` (`"Replace with pgvector cosine similarity once embeddings are wired"`) is resolved by routing vector search through Qdrant instead of pgvector. This avoids adding pgvector as a PostgreSQL extension dependency while providing a purpose-built vector search backend.

The data flow:
1. Document ingestion writes structured metadata to PgMemory (episodic memory of the ingestion event, entity relations for document cross-references)
2. Document embeddings write to Qdrant (vector search)
3. Document structure writes to OpenViking (hierarchical context management)
4. On recall, Qdrant finds relevant vectors, OpenViking serves the right tier, PgMemoryStore provides precedent context

---

## 8. Layer 4 — Tiered Context Retrieval

### The Retrieval Problem

An agent asks: "What are the indemnification obligations in the Acme merger agreement?"

A naive system returns the full indemnification section (3,000 tokens) plus related sections (5,000 more tokens). 8,000 tokens consumed, most of it unnecessary for an initial answer.

### The Tiered Solution

**Phase 1: Candidate Discovery (cheap)**
- Qdrant kNN search returns top-20 section URIs with scores (cost: one embedding call)
- OpenViking hierarchical search returns top-15 section URIs with traversal path (cost: intent analysis LLM call + directory-scoped vector searches)
- Merge via reciprocal rank fusion: ~25 unique candidates

**Phase 2: L0 Scan (very cheap, ~2,500 tokens for 25 candidates)**
- Load L0 abstract for all 25 candidates
- Each L0 is ~100 tokens: "This section establishes mutual indemnification obligations with a $10M aggregate cap, excluding IP claims and willful misconduct."
- Agent (or our reranker) can now eliminate 15 candidates as irrelevant
- 10 candidates remain

**Phase 3: L1 Expansion (moderate, ~10,000 tokens for 10 candidates)**
- Load L1 overview for the 10 surviving candidates
- Each L1 is ~1,000 tokens: key obligations, defined terms used, cross-references, important amounts/dates
- Agent can now answer most questions from L1 alone
- If the agent needs exact clause language, it requests L2 for 1-3 specific sections

**Phase 4: L2 Detail (on demand, targeted)**
- Load full L2 text for only the 1-3 sections the agent explicitly needs
- This is the original clause language with full context

**Token budget comparison** (using `token_budget=6144`, the recommended default for complex queries):
| Approach | Tokens consumed |
|---|---|
| Full document in context | ~80,000 |
| Traditional RAG (top-10 chunks) | ~20,000 |
| This system (L0 scan → L1 for 10 → L2 for 2) | ~5,500 |

The `recall_context` default `token_budget` of 6144 is chosen to comfortably fit this profile:
25 × L0 (2,500) + 10 × L1 (up to 10,000, trimmed to fit) + 1-2 × L2 (on demand, returned as
`L2_available` hints rather than inline content). For simple lookups, `token_budget=2048` returns
L0 only; for deep research set `token_budget=12288` to inline more L1s.

### Retrieval Flow Detail

```
Agent query: "What are the indemnification obligations?"
          │
          ▼
┌─────────────────────────────────────────┐
│ 1. EMBED QUERY                          │
│    model: text-embedding-3-large        │
│    output: 3072-dim dense vector        │
└────────┬────────────────────────────────┘
         │
    ┌────▼──────┐          ┌──────────────┐
    │ 2A. QDRANT│          │ 2B. OPENVIKING│
    │           │          │              │
    │ kNN search│          │ search()     │
    │ top_k=20  │          │ - intent     │
    │ filter:   │          │   analysis   │
    │  doc_ids  │          │ - directory  │
    │  level<=1 │          │   traversal  │
    │           │          │ - recursive  │
    │ Returns:  │          │   drill-down │
    │ [(uri,    │          │              │
    │   score)] │          │ Returns:     │
    │           │          │ QueryResult  │
    └────┬──────┘          └──────┬───────┘
         │                        │
         └───────────┬────────────┘
                     │
          ┌──────────▼──────────────┐
          │ 3. RANK FUSION          │
          │                         │
          │ Reciprocal Rank Fusion: │
          │ score = Σ 1/(k + rank)  │
          │ for each result set     │
          │                         │
          │ Deduplicate by URI      │
          │ Sort by fused score     │
          │ Top-N candidates        │
          └──────────┬──────────────┘
                     │
          ┌──────────▼──────────────┐
          │ 4. TIERED ASSEMBLY      │
          │                         │
          │ Budget: 6144 tokens     │
          │                         │
          │ Step 1: Load all L0s    │
          │   25 × ~100 = 2,500 t  │
          │                         │
          │ Step 2: Remaining budget│
          │   6144 - 2500 = 3,644 t │
          │                         │
          │ Step 3: Promote top     │
          │   candidates to L1      │
          │   ~1,000 t each         │
          │   Promote top 3         │
          │                         │
          │ Step 4: Remaining ~644t │
          │   Note L2 available as  │
          │   hints for agent to    │
          │   explicitly request    │
          └──────────┬──────────────┘
                     │
          ┌──────────▼──────────────┐
          │ 5. RESPONSE             │
          │                         │
          │ context_blocks:         │
          │  - 2 sections at L1     │
          │  - 8 sections at L0     │
          │ total_tokens: 3,847     │
          │ retrieval_trajectory:   │
          │   (full debug info)     │
          └─────────────────────────┘
```

### Relationship to Existing Retrieval

The existing `SimilarityEngine` in `memory/similarity.py` uses sklearn TF-IDF or keyword overlap for memory recall. It was always intended as a placeholder — the code comments reference pgvector as the intended upgrade path.

This system replaces `SimilarityEngine` for document retrieval with Qdrant + OpenViking's `HierarchicalRetriever`. For backward compatibility with the existing `PgMemoryStore.recall()` method (used by the `recall_memory` skill and existing MCP tools), two options:

1. **Qdrant adapter:** Implement a `QdrantSimilarityEngine` that implements the same `search(query, top_k) -> [(id, score)]` interface but routes through Qdrant. Drop-in replacement for `SimilarityEngine`.
2. **Parallel path:** Keep `PgMemoryStore.recall()` as-is for regulatory memory search (it works fine for the existing use case). Document retrieval uses the new dual-engine path exclusively.

Recommendation: Option 2 initially (lower risk, faster ship), migrate to Option 1 once the Qdrant integration is proven in production.

---

## 9. Layer 5 — Process Execution Engine

### What Is a Process?

A process is a structured, multi-step document review procedure stored as a markdown definition. It codifies institutional knowledge — the checklist a senior partner uses, the review protocol a compliance officer follows, the intake procedure a medical practice requires.

### Process Definition Format

```markdown
---
name: contract_review_checklist
version: "1.0"
doc_types: [legal]
description: Standard M&A contract review checklist
author: Jane Smith, Partner
steps: 28
---

# Contract Review Checklist

## Step 1: Parties & Recitals
- **instruction**: Identify all parties, their roles, and the recitals. Confirm legal entity names match throughout.
- **retrieval_query**: parties recitals definitions legal entity names
- **target_sections**: [definitions, recitals]
- **depth**: overview
- **output**:
  - parties: list of {name, role, entity_type}
  - recitals_summary: string
  - name_consistency: pass | fail
- **depends_on**: []

## Step 2: Definitions
- **instruction**: Review all defined terms. Flag any that are circular, ambiguous, or missing.
- **retrieval_query**: definitions defined terms
- **target_sections**: [definitions]
- **depth**: detail
- **output**:
  - defined_terms: list of {term, definition_summary}
  - flagged_terms: list of {term, issue}
- **depends_on**: [1]

## Step 13: Limitation of Liability
- **instruction**: Review liability cap provisions. Check for: (1) aggregate cap amount or formula, (2) exclusions from cap (IP indemnity, confidentiality breach, willful misconduct), (3) consequential damages waiver, (4) mutual vs one-sided structure.
- **retrieval_query**: limitation of liability cap consequential damages waiver exclusions
- **target_sections**: [liability, indemnification]
- **depth**: detail
- **output**:
  - cap_amount: string
  - cap_formula: string
  - exclusions: list of string
  - consequential_waiver: boolean
  - mutual: boolean
  - concerns: list of string
- **depends_on**: [12]

...
```

### Process Storage

Process definitions are stored in OpenViking at `viking://processes/{process_name}/definition.md`. They are parsed on registration, validated for step ordering and dependency consistency, and indexed (L0/L1 generated for discoverability).

This also means processes are searchable. An agent can ask "what review processes are available for medical documents?" and the retrieval system finds relevant processes via their L0/L1 metadata.

### Process Execution State

When an agent starts a process, execution state is tracked at `viking://sessions/{session_id}/progress/{process_name}.json`:

```json
{
  "process_name": "contract_review_checklist",
  "session_id": "abc-123",
  "doc_ids": ["doc-456"],
  "started_at": "2026-04-08T14:30:00Z",
  "current_step": 13,
  "steps": [
    {
      "step_number": 1,
      "name": "Parties & Recitals",
      "status": "pass",
      "completed_at": "2026-04-08T14:32:00Z",
      "findings": {
        "parties": [
          {"name": "Acme Corp", "role": "Buyer", "entity_type": "Delaware C-Corp"},
          {"name": "Widget Inc", "role": "Target", "entity_type": "California LLC"}
        ],
        "recitals_summary": "Standard M&A recitals. Buyer acquiring 100% of Target equity.",
        "name_consistency": "pass"
      },
      "tokens_used": 1847
    },
    {
      "step_number": 2,
      "name": "Definitions",
      "status": "flagged",
      "completed_at": "2026-04-08T14:35:00Z",
      "findings": {
        "defined_terms": ["..."],
        "flagged_terms": [
          {"term": "Material Adverse Effect", "issue": "Carve-outs may be overly broad — includes 'general economic conditions' without qualification"}
        ]
      },
      "tokens_used": 3201
    }
  ]
}
```

### Process as a Skill

The process engine integrates with the existing `AgentRuntime` skill framework. A new `DocumentProcessSkill` registers in `ALL_SKILLS`:

```python
class DocumentProcessSkill(Skill):
    metadata = SkillMetadata(
        name="follow_process",
        description="Execute a step in a registered document review process",
        version="1.0.0",
        permissions=Permission.LLM_READ | Permission.MEMORY_READ | Permission.MEMORY_WRITE | Permission.STATE_READ | Permission.STATE_WRITE,
        latency=LatencyClass.MODERATE,
        parameters=[
            SkillParameter("process_name", "str", "Name of the process to execute"),
            SkillParameter("doc_ids", "list[str]", "Documents to process against"),
            SkillParameter("session_id", "str", "Session ID", required=False),
            SkillParameter("action", "str", "start|next|skip|status|complete", required=False, default="start"),
            SkillParameter("step_result", "dict", "Agent findings for current step", required=False),
        ],
        returns="dict — current step with context and progress",
        tags=["process", "orchestration", "document"],
    )
```

This means process execution gets the same Permission checks, AuditLog entries, SecurityPolicy enforcement, and budget tracking as every other skill in the system.

---

## 10. Layer 6 — Session & Memory Lifecycle

### Session Flow

```
Agent connects via MCP
         │
         ▼
    Create session
    (viking://sessions/{id}/)
         │
         ▼
┌────────────────────────┐
│ Agent calls tools       │
│                         │
│ ingest_document()       │──→ Documents stored in OV + Qdrant
│ recall_context()        │──→ Tiered retrieval from both engines
│ follow_process()        │──→ Process steps with targeted retrieval
│                         │
│ Each tool call logged   │──→ messages.jsonl
│ as Message with Parts:  │    (TextPart, ContextPart, ToolPart)
└────────┬────────────────┘
         │
         ▼  (auto-commit threshold reached, or explicit commit)
┌────────────────────────┐
│ Session Commit          │
│                         │
│ Phase 1 (synchronous):  │
│   Snapshot messages     │
│   Write to archive      │
│   Generate L0/L1 for    │
│   the archive segment   │
│                         │
│ Phase 2 (async):        │
│   Extract memories:     │
│   - User preferences    │──→ viking://user/memories/preferences/
│   - Entity references   │──→ viking://user/memories/entities/
│   - Review patterns     │──→ viking://agent/memories/patterns/
│   - Case findings       │──→ viking://agent/memories/cases/
│                         │
│   Also:                 │
│   - Store episodic      │──→ PgMemoryStore.store_episodic()
│   - Extract entities    │──→ PgMemoryStore._add_relation()
│   - Embed memories      │──→ Qdrant ns_sessions collection
└────────────────────────┘
```

### Memory Dual-Write

When memories are extracted from a session commit, they are written to three places:

1. **OpenViking** — the memory content as a file under the appropriate scope (`viking://user/memories/entities/acme-corp`). This enables hierarchical browsing ("show me all entities I've encountered") and tiered access (L0 for scanning, L1 for context).

2. **PgMemoryStore** — a `PgMemory` row with structured content (JSON), embedding_text (for search), and relational metadata. This enables SQL queries, belief tracking, feedback loops, and governance audit.

3. **Qdrant** — an embedding in the `ns_sessions` collection for fast semantic recall in future sessions. When a new session starts and the agent asks something related to a past review, Qdrant finds the relevant memory in milliseconds.

### Relationship to Existing Memory Types

The existing `MemoryType` enum (`EPISODIC`, `ENTITY`, `PRECEDENT`) maps directly:

| Memory Type | Document Context Example |
|---|---|
| `EPISODIC` | "On 2026-04-08, reviewed Acme merger agreement. Found liability cap of $10M with broad exclusions. Flagged MAE definition as overly broad." |
| `ENTITY` | "Acme Corp: Delaware C-Corp, acquiring Widget Inc. Represented by Davis Polk. Standard M&A terms." |
| `PRECEDENT` | "In the Acme review, the partner corrected our classification of the IP carve-out from 'standard' to 'aggressive' — feedback recorded for future reviews of similar clauses." |

The existing evidence ledger (`EvidenceLedgerEntry`) with its multi-dimensional scoring (`strength_score`, `novelty_score`, `source_authority`, `recency_score`, `jurisdiction_relevance`, `business_line_proximity`) can score document-derived memories the same way it scores regulatory filing memories. A precedent from a prior contract review has `source_authority` (was it corrected by a partner?), `recency_score` (how recent?), and `jurisdiction_relevance` (same jurisdiction?).

---

## 11. Integration with Existing NaturalSentinel Stack

### Skill Registration

New skills added to `ALL_SKILLS` in `backend/app/naturalsentinel/skills/__init__.py`:

| Skill | Permission Flags | Latency | Purpose |
|---|---|---|---|
| `IngestDocumentSkill` | `FILE_READ \| LLM_WRITE \| MEMORY_WRITE` | `BATCH` | Parse, structure, tier, index a document |
| `RecallDocumentContextSkill` | `MEMORY_READ \| LLM_READ` | `MODERATE` | Dual-engine retrieval with tiered assembly |
| `DocumentProcessSkill` | `LLM_READ \| MEMORY_READ \| MEMORY_WRITE \| STATE_READ \| STATE_WRITE` | `MODERATE` | Execute process steps |
| `RegisterProcessSkill` | `FILE_WRITE \| STATE_WRITE` | `FAST` | Store and validate a process definition |
| `DocumentStatusSkill` | `STATE_READ` | `INSTANT` | Query document ingestion status |

These register alongside the existing 35 skills. The `AgentRuntime` treats them identically — same Permission resolution, same AuditLog, same SecurityPolicy budget tracking.

### Dependency Injection

New dependencies in `backend/app/api/deps.py`:

```python
def get_openviking_client() -> openviking.SyncOpenViking:
    """Singleton OpenViking embedded client."""
    ...

def get_qdrant_client() -> qdrant_client.QdrantClient:
    """Singleton Qdrant client connected to compose service."""
    ...

OpenVikingDep = Annotated[openviking.SyncOpenViking, Depends(get_openviking_client)]
QdrantDep = Annotated[qdrant_client.QdrantClient, Depends(get_qdrant_client)]
```

These are available to route handlers and can be threaded through to skills via `SkillContext`. The `SkillContext` dataclass gains optional `openviking` and `qdrant` fields, populated only when the skill has the appropriate permissions.

### Router Registration

New router in `backend/app/api/routes/documents.py`, registered in `main.py`:

```python
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
```

This provides REST endpoints alongside the MCP tools — same functionality, different interface. The REST API is useful for dashboard UIs, batch operations, and non-MCP agent integrations.

### Configuration Extensions

New fields in `Settings` (`core/config.py`):

```python
# Qdrant
QDRANT_URL: str = "http://localhost:6333"
QDRANT_API_KEY: str | None = None
QDRANT_COLLECTION_PREFIX: str = "ns_"

# OpenViking
OPENVIKING_WORKSPACE: str = "./openviking_data"
OPENVIKING_VLM_PROVIDER: str = "litellm"
OPENVIKING_VLM_MODEL: str = "claude-sonnet-4-6"
OPENVIKING_EMBEDDING_PROVIDER: str = "openai"
OPENVIKING_EMBEDDING_MODEL: str = "text-embedding-3-large"
OPENVIKING_EMBEDDING_DIMENSION: int = 3072
```

### Docker Compose Updates

The existing `qdrant` service in `compose.yml` is already configured. Additions:

```yaml
services:
  backend:
    environment:
      - QDRANT_URL=http://qdrant:6333
      - OPENVIKING_WORKSPACE=/data/openviking
    volumes:
      - openviking-data:/data/openviking

volumes:
  openviking-data:
```

No separate OpenViking server container needed — the embedded Python client runs inside the backend process.

---

## 12. Data Models

### New SQLModel Tables

#### `PgDocument` (`ns_documents`)

Tracks **user-uploaded documents** at the relational level (contracts, policies, medical records).
Complements the OpenViking filesystem representation.

> **Not used for regulatory filings.** State and federal regulatory filings are tracked via the
> existing `ns_memories` table (episodic memory of each ingestion event) and the `ns_state_filings`
> Qdrant collection. `PgDocument` is for documents the user explicitly uploads, not for
> programmatically-fetched regulatory content. This keeps the two ingestion tracks independent.

```python
class PgDocument(SQLModel, table=True):
    __tablename__ = "ns_documents"

    doc_id: str       # UUID PK
    title: str
    doc_type: str     # "legal", "medical", "compliance", "generic"
    file_name: str    # Original filename
    file_size: int    # Bytes
    uri: str          # viking://documents/{doc_id} — indexed
    section_count: int
    status: str       # "processing", "ready", "error"
    metadata_json: dict  # sa.JSON — client_name, matter_id, tags, etc.
    structure_json: dict # sa.JSON — section tree for quick access
    created_at: datetime # timezone-aware
    updated_at: datetime
    created_by: str   # User ID
```

#### `PgProcessDefinition` (`ns_process_definitions`)

```python
class PgProcessDefinition(SQLModel, table=True):
    __tablename__ = "ns_process_definitions"

    name: str          # PK — unique process identifier
    version: str
    description: str
    doc_types: list    # sa.JSON — applicable document types
    step_count: int
    definition_md: str # Full markdown definition
    uri: str           # viking://processes/{name}
    created_at: datetime
    updated_at: datetime
    created_by: str
```

#### `PgProcessExecution` (`ns_process_executions`)

```python
class PgProcessExecution(SQLModel, table=True):
    __tablename__ = "ns_process_executions"

    execution_id: str   # UUID PK
    session_id: str     # FK to session — indexed
    process_name: str   # FK to process definition — indexed
    doc_ids: list       # sa.JSON
    current_step: int
    total_steps: int
    completed_steps: int
    flagged_steps: int
    status: str         # "in_progress", "completed", "paused", "abandoned"
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    findings_json: dict  # sa.JSON — aggregated findings
```

These tables are registered in `alembic/env.py` for migration autogeneration.

### Pydantic Schemas

Following the project convention (`<Name>Base` → `<Name>Create` → `<Name>Public`):

```python
class DocumentBase(SQLModel):
    title: str
    doc_type: str
    metadata_json: dict = {}

class DocumentCreate(DocumentBase):
    file_name: str
    file_size: int

class DocumentPublic(DocumentBase):
    doc_id: str
    uri: str
    section_count: int
    status: str
    structure_json: dict
    created_at: datetime

class ProcessDefinitionBase(SQLModel):
    name: str
    description: str
    doc_types: list[str] = []

class ProcessDefinitionCreate(ProcessDefinitionBase):
    definition_md: str

class ProcessExecutionPublic(SQLModel):
    execution_id: str
    session_id: str
    process_name: str
    current_step: int
    total_steps: int
    completed_steps: int
    flagged_steps: int
    status: str
    started_at: datetime
```

---

## 13. Configuration & Environment

### New Environment Variables

| Variable | Default | Description |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | Qdrant gRPC/HTTP endpoint |
| `QDRANT_API_KEY` | `None` | Qdrant API key (optional, for Qdrant Cloud) |
| `QDRANT_COLLECTION_PREFIX` | `ns_` | Prefix for all Qdrant collections |
| `OPENVIKING_WORKSPACE` | `./openviking_data` | Local filesystem path for AGFS storage |
| `OPENVIKING_VLM_PROVIDER` | `litellm` | VLM provider for L0/L1 generation |
| `OPENVIKING_VLM_MODEL` | `claude-sonnet-4-6` | VLM model name |
| `OPENVIKING_EMBEDDING_PROVIDER` | `openai` | Embedding provider |
| `OPENVIKING_EMBEDDING_MODEL` | `text-embedding-3-large` | Embedding model name |
| `OPENVIKING_EMBEDDING_DIMENSION` | `3072` | Embedding vector dimension |
| `OPENVIKING_VLM_MAX_CONCURRENT` | `100` | Max concurrent VLM calls for L0/L1 generation |
| `OPENVIKING_EMBEDDING_MAX_CONCURRENT` | `10` | Max concurrent embedding calls |

### Generated OpenViking Config

The backend generates `ov.conf` at startup from these environment variables, written to `{OPENVIKING_WORKSPACE}/ov.conf`. This means operators configure via `.env` (consistent with existing NaturalSentinel patterns) rather than managing a separate OpenViking config file.

---

## 14. Security & Compliance

### Document-Level Access Control

Documents are scoped to the user who ingested them via `created_by` on `PgDocument`. The MCP server enforces that recall and process execution only access documents owned by the authenticated user (via `CurrentUser` dependency).

For shared documents (firm-wide policies, standard templates), documents can be tagged with `visibility: "shared"` in metadata. The retrieval layer checks visibility before returning results.

### Audit Trail

Every document operation is audit-logged via the existing `PgAuditEvent` table and `AuditLog`:

| Event Type | Payload |
|---|---|
| `DOCUMENT_INGESTED` | doc_id, file_name, doc_type, section_count, user_id |
| `DOCUMENT_RECALLED` | doc_id, query, sections_returned, tokens_used, user_id |
| `PROCESS_STARTED` | process_name, doc_ids, session_id, user_id |
| `PROCESS_STEP_COMPLETED` | process_name, step_number, status, findings_summary |
| `PROCESS_COMPLETED` | process_name, session_id, total_steps, flagged_count |

### Data Residency

All document content stays on-premises:
- OpenViking AGFS stores documents on the local filesystem (or S3 if configured)
- Qdrant stores vectors locally (Docker volume or self-hosted cluster)
- PostgreSQL stores metadata locally

Only embedding and VLM API calls leave the network. For fully air-gapped deployments, configure `ollama` as both VLM and embedding provider.

### Encryption

OpenViking supports optional content encryption per account. When enabled, all documents stored in AGFS are encrypted at rest. The encryption key is managed by the `encryptor` passed to `init_viking_fs()`.

---

## 15. Deployment Architecture

### Development (Local)

```
docker compose up -d        # Starts: db, qdrant, backend, frontend
                             # OpenViking runs embedded in backend process
                             # Qdrant on port 6333
                             # Backend on port 8000
                             # Frontend on port 5173
```

### Production

```
┌─────────────┐     ┌───────────────┐     ┌──────────────┐
│  Frontend    │     │  Backend      │     │  PostgreSQL   │
│  (CDN/S3)   │────→│  (FastAPI)    │────→│  (RDS/Cloud)  │
│              │     │  + OpenViking │     │               │
└─────────────┘     │  (embedded)   │     └──────────────┘
                    └───────┬───────┘
                            │
                    ┌───────▼───────┐
                    │  Qdrant       │
                    │  (dedicated   │
                    │   instance)   │
                    └───────────────┘

Storage:
  - OpenViking AGFS → S3 bucket (persistent, encrypted)
  - Qdrant → dedicated volume (SSD-backed)
  - PostgreSQL → managed instance
```

For high-throughput deployments (many concurrent users, large document volumes), OpenViking can alternatively run as a standalone HTTP server (`openviking-server`) and the backend connects via `SyncHTTPClient(url=...)` instead of the embedded client.

---

## 16. Migration & Rollout Plan

### Phase 1: Foundation (Qdrant + OpenViking Integration)

- Wire Qdrant client into `deps.py` with collection creation on startup
- Embed OpenViking client into backend with config generation from `.env`
- Implement `QdrantSimilarityEngine` as drop-in for existing `SimilarityEngine`
- Add new config fields to `Settings`
- Add `PgDocument`, `PgProcessDefinition`, `PgProcessExecution` models
- Generate Alembic migration
- Validate: existing 35 skills and 6 MCP tools continue to work unchanged

### Phase 2: Document Ingestion Pipeline

- Implement structure extractors (legal, medical, compliance, generic)
- Build hierarchy-to-OpenViking directory writer
- Implement dual-write to Qdrant + OpenViking
- Implement `IngestDocumentSkill` and `DocumentStatusSkill`
- Validate: ingest a PDF contract, browse its structure in OpenViking, search sections in Qdrant

### Phase 3: Tiered Retrieval

- Implement dual-path retrieval (Qdrant kNN + OpenViking hierarchical)
- Implement rank fusion and tiered assembly
- Implement `RecallDocumentContextSkill`
- Validate: query returns relevant sections at appropriate tier with correct token budget

### Phase 4: Process Engine

- Implement process definition parser
- Implement process state tracking
- Implement `DocumentProcessSkill` and `RegisterProcessSkill`
- Ship 3 built-in process definitions (contract review, medical records review, compliance gap analysis)
- Validate: complete a full process execution across multiple agent turns

### Phase 5: MCP Server

- Build the new MCP server with all 6 tools, resources, and prompts
- Wire to the skill layer (MCP tools call skills, skills call engines)
- Test with Claude Code, Claude Desktop, and Codex
- Validate: end-to-end flow from file attachment to completed process

### Phase 6: Memory Lifecycle

- Implement session commit with triple-write (OpenViking + PgMemoryStore + Qdrant)
- Implement cross-session memory recall
- Implement precedent learning from process corrections
- Validate: start a new session, automatically recall relevant findings from prior reviews

---

*This document is a living specification. Each layer section should be updated as implementation decisions are made and validated.*

---

## 17. Source-Grounded Analysis & Line-Level Citation

### Problem

LLM-generated analysis conclusions are only as trustworthy as the evidence they cite. Without
explicit back-references to the source document, there is no way to verify that a finding is
grounded in the actual regulatory text — or to audit which passage drove a compliance decision.
This matters especially for regulatory documents where a single word difference ("shall" vs "may",
"licensee" vs "registrant") can change the compliance obligation entirely.

### Design Goal

Every conclusion in an `ImpactAssessment` and every entry in a `MonitorResult.evidence_ledger`
must be traceable to a specific passage in the original source document, identified by:
- `source_url` — direct URL to the original filing
- `viking_uri` — stable OpenViking URI to the exact passage
- `line_start` / `line_end` — line numbers within the source text
- `excerpt` — the verbatim text passage that grounds the conclusion

---

### Position-Aware Chunking

When a regulatory document is ingested (Layer 2), the structure extractor splits it into chunks
at paragraph or semantic-section boundaries. Each chunk carries position metadata computed during
extraction:

```python
@dataclass
class DocumentChunk:
    chunk_id: str          # "{doc_id}:{section_path}:{chunk_index}"
    doc_id: str
    section_path: str      # e.g. "Section 3 > Subsection 2(b)"
    text: str              # verbatim original text — always L2 content, never summarised
    line_start: int        # 1-indexed line number in the original source file
    line_end: int
    char_offset_start: int # byte offset from start of source file
    char_offset_end: int
    page_number: int | None  # for PDF sources; None for HTML/text sources
```

`DocumentChunk` always represents verbatim source text (L2). The L0 and L1 tiers are
**generated from** chunks after ingestion via the VLM pipeline (Stage 5 of Layer 2).
`DocumentChunk` is the input to that pipeline, not an output of it — so it has no `level` field.

For PDFs: `page_number` is populated from the PDF parser; `line_start`/`line_end` are
line numbers within that page.

For HTML/text: line numbers are computed by counting `\n` characters up to the chunk's
`char_offset_start` in the raw source.

**Chunking rules:**
- Maximum chunk size: 512 tokens (fits comfortably in embedding context)
- Minimum chunk size: 50 tokens (avoid embedding fragments)
- Split on paragraph boundaries first; fall back to sentence boundaries if a paragraph
  exceeds the maximum
- Overlapping context: each chunk carries the last sentence of the preceding chunk as a
  prefix (not counted in line numbers) to prevent citation loss at boundaries

---

### Qdrant Payload Schema (Extended)

The `ns_documents` and `ns_state_filings` collections store one point per chunk. The payload
includes all citation metadata needed to back-reference a conclusion to its source:

```json
{
  "doc_id":              "ca-dfpi-2026-04-11",
  "chunk_id":            "ca-dfpi-2026-04-11:section_3:para_2:0",
  "viking_uri":          "viking://state_regulations/CA/financial_services/ca-dfpi-2026-04-11/section_3/para_2",
  "source_url":          "https://dfpi.ca.gov/filings/2026-04-11-rule.pdf",
  "section_path":        "Section 3 > Paragraph 2",
  "line_start":          145,
  "line_end":            167,
  "char_offset_start":   8340,
  "char_offset_end":     9120,
  "page_number":         4,
  "excerpt":             "No licensee shall charge a fee exceeding...",
  "level":               2,
  "doc_type":            "final_rule",
  "jurisdiction":        "state",
  "state_code":          "CA",
  "industry_sectors":    ["financial_services", "insurance"],
  "published_date":      "2026-04-11",
  "title":               "DFPI Final Rule — Consumer Fee Limits"
}
```

The `excerpt` field stores the first 200 characters of the chunk verbatim. This lets a
citation be shown to a user without a round-trip to OpenViking or the source URL.

---

### OpenViking L2 Storage for Source Provenance

The full original text of every chunk is stored at L2 in OpenViking. The directory hierarchy
mirrors the document structure:

```
viking://state_regulations/{state_code}/{sector}/{doc_id}/
  ├── .abstract.md            (L0 — ~100 tokens, generated)
  ├── .overview.md            (L1 — ~1000 tokens, generated)
  ├── metadata.json           (doc_id, source_url, published_date, jurisdiction, ...)
  ├── section_1/
  │   └── .overview.md
  ├── section_2/
  └── section_3/
      ├── .overview.md
      └── para_2/
          ├── full_text.md    (L2 — verbatim original text, lines 145–167)
          └── metadata.json   (chunk_id, line_start, line_end, char_offset_start, ...)
```

`full_text.md` contains the **verbatim original text** — no summarisation, no paraphrasing.
This ensures that when a citation is surfaced to a user, it reflects exactly what was
published by the regulatory body.

The `metadata.json` at the chunk level duplicates the position fields from the Qdrant
payload. This means citation metadata is recoverable from either storage system independently.

---

### Extended `EvidenceLedgerEntry`

`backend/app/naturalsentinel/evidence.py` — add citation location fields:

```python
class EvidenceLedgerEntry(BaseModel):
    evidence_id: str
    source_type: str

    # Citation location — populated for all document-grounded evidence
    source_url: str = ""            # direct URL to original document
    viking_uri: str = ""            # viking:// URI for OpenViking retrieval
    line_start: int | None = None   # line in original source
    line_end: int | None = None
    page_number: int | None = None  # for PDF sources
    excerpt: str = ""               # verbatim passage (≤200 chars)
    section_path: str = ""          # human-readable section label

    # Existing scoring fields (unchanged)
    supports: list[str] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)
    strength_score: float = Field(default=0.0, ge=0.0, le=1.0)
    novelty_score: float = Field(default=0.0, ge=0.0, le=1.0)
    trace: list[str] = Field(default_factory=list)
    source_authority: float = Field(default=0.0, ge=0.0, le=1.0)
    recency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    policy_finality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    jurisdiction_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    business_line_proximity: float = Field(default=0.0, ge=0.0, le=1.0)
    historical_predictive_usefulness: float = Field(default=0.0, ge=0.0, le=1.0)
    contradiction_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
```

---

### Citation Flow Through Analysis

```
1. RETRIEVAL
   Qdrant kNN search → top-k chunks (each has chunk_id, viking_uri, line_start/end, excerpt)

2. CONTEXT ASSEMBLY
   Chunks are formatted for the LLM with citation anchors:
   "[CITE:ca-dfpi-2026-04-11:section_3:para_2:0]
    No licensee shall charge a fee exceeding..."

3. LLM ANALYSIS (AnalyzeFilingSkill)
   System prompt instructs: "For every finding, you MUST cite the chunk IDs that
   support it using [CITE:<chunk_id>] markers. Do not make claims that are not
   grounded in the provided chunks."

4. CITATION EXTRACTION
   Post-process the LLM response to extract [CITE:...] markers → resolve each
   chunk_id to its Qdrant payload → populate EvidenceLedgerEntry with
   source_url, viking_uri, line_start, line_end, excerpt.

5. VERIFICATION
   Any ImpactAssessment.action_item or risk_summary clause that contains no
   resolved citation is flagged with confidence penalty and marked
   provenance: {"status": "ungrounded"}.

6. OUTPUT
   MonitorResult.evidence_ledger contains fully-resolved EvidenceLedgerEntry
   objects. The frontend can render "Source: CA DFPI Final Rule, §3 ¶2 (lines 145–167)"
   as a clickable link to source_url#L145.
```

---

### Audit Trail Extension

The existing `DOCUMENT_RECALLED` audit event is extended with citation counts:

| Event Type | Additional Payload |
|---|---|
| `ANALYSIS_COMPLETED` | filing_id, citation_count, ungrounded_count, evidence_ledger_ids |
| `CITATION_RESOLVED` | chunk_id, viking_uri, source_url, line_start, line_end |
| `UNGROUNDED_FINDING` | filing_id, finding_text, confidence_penalty |

---

## 18. State-Level Regulatory Monitoring by Industry Sector

### Problem

Federal regulatory monitoring misses a significant portion of compliance obligations.
State-level regulations — from state banking commissions, insurance departments, health
agencies, and public utility commissions — often impose stricter requirements than federal
rules and frequently diverge across states. A business operating in multiple states faces
a patchwork of obligations that no single federal feed captures.

### Design Goal

Extend NaturalSentinel to monitor US state-level regulatory filings, tagged by **industry
sector**, so customers can see exactly which states are making regulatory changes relevant
to their business — and receive the same grounded, cited analysis as federal filings.

---

### New Domain Models

`backend/app/naturalsentinel/models.py`:

```python
class StateCode(Enum):
    AL = "AL"  # Alabama          AK = "AK"  # Alaska
    AZ = "AZ"  # Arizona          AR = "AR"  # Arkansas
    CA = "CA"  # California       CO = "CO"  # Colorado
    CT = "CT"  # Connecticut      DE = "DE"  # Delaware
    FL = "FL"  # Florida          GA = "GA"  # Georgia
    HI = "HI"  # Hawaii           ID = "ID"  # Idaho
    IL = "IL"  # Illinois         IN = "IN"  # Indiana
    IA = "IA"  # Iowa             KS = "KS"  # Kansas
    KY = "KY"  # Kentucky         LA = "LA"  # Louisiana
    ME = "ME"  # Maine            MD = "MD"  # Maryland
    MA = "MA"  # Massachusetts    MI = "MI"  # Michigan
    MN = "MN"  # Minnesota        MS = "MS"  # Mississippi
    MO = "MO"  # Missouri         MT = "MT"  # Montana
    NE = "NE"  # Nebraska         NV = "NV"  # Nevada
    NH = "NH"  # New Hampshire    NJ = "NJ"  # New Jersey
    NM = "NM"  # New Mexico       NY = "NY"  # New York
    NC = "NC"  # North Carolina   ND = "ND"  # North Dakota
    OH = "OH"  # Ohio             OK = "OK"  # Oklahoma
    OR = "OR"  # Oregon           PA = "PA"  # Pennsylvania
    RI = "RI"  # Rhode Island     SC = "SC"  # South Carolina
    SD = "SD"  # South Dakota     TN = "TN"  # Tennessee
    TX = "TX"  # Texas            UT = "UT"  # Utah
    VT = "VT"  # Vermont          VA = "VA"  # Virginia
    WA = "WA"  # Washington       WV = "WV"  # West Virginia
    WI = "WI"  # Wisconsin        WY = "WY"  # Wyoming
    DC = "DC"  # District of Columbia

class Jurisdiction(Enum):
    FEDERAL = "federal"
    STATE   = "state"

class IndustrySector(Enum):
    FINANCIAL_SERVICES = "financial_services"
    HEALTHCARE         = "healthcare"
    INSURANCE          = "insurance"
    ENERGY_UTILITIES   = "energy_utilities"
    REAL_ESTATE        = "real_estate"
    TECHNOLOGY         = "technology"
    MANUFACTURING      = "manufacturing"
    TRANSPORTATION     = "transportation"
```

`RegulatoryFiling` is extended with three new optional fields:

```python
class RegulatoryFiling(BaseModel):
    ...
    jurisdiction: Jurisdiction = Jurisdiction.FEDERAL
    state_code: StateCode | None = None          # None for federal filings
    industry_sectors: list[str] = Field(default_factory=list)  # IndustrySector values
```

---

### Sector → Agency Mapping

`backend/app/naturalsentinel/fetchers/state_domains.py` (new file):

```python
# Which industry sectors map to which federal regulatory domains
# NOTE: MVP mapping — intentionally conservative. Expand in Phase 8 based on
# customer feedback. "technology" in particular will need FTC and NIST once
# those domains are added to RegulatoryDomain.
SECTOR_TO_FEDERAL_DOMAINS: dict[str, list[str]] = {
    "financial_services": ["sec", "cfpb", "fed", "fdic", "occ", "finra", "cftc", "basel"],
    "healthcare":         ["fda"],
    "insurance":          ["cfpb", "fhfa"],
    "energy_utilities":   ["epa"],
    "real_estate":        ["fhfa", "cfpb", "fdic"],
    "transportation":     ["ustr", "epa"],
    "manufacturing":      ["epa", "ustr"],
    "technology":         ["sec", "cfpb", "ustr"],
}

# State RSS feeds by state, each tagged with relevant sectors
# Priority states for MVP: CA, NY, TX, FL, IL, MA
STATE_AGENCY_RSS_FEEDS: dict[str, list[dict]] = {
    "CA": [
        {"url": "https://www.oal.ca.gov/rss/regulations.xml",
         "agency": "CA OAL", "sectors": ["financial_services", "insurance", "healthcare"]},
        {"url": "https://dfpi.ca.gov/feed/",
         "agency": "CA DFPI", "sectors": ["financial_services", "insurance"]},
    ],
    "NY": [
        {"url": "https://www.dfs.ny.gov/reports_and_publications/rss",
         "agency": "NY DFS", "sectors": ["financial_services", "insurance"]},
    ],
    "TX": [
        {"url": "https://www.sos.texas.gov/texreg/rss/",
         "agency": "TX SOS", "sectors": ["financial_services", "insurance", "energy_utilities"]},
    ],
    # Additional states added in Phase 2 rollout
}
```

---

### Data Sources

Four complementary sources are used, each covering a different slice of state regulatory activity:

#### 1. Open States API (`fetchers/live/open_states.py`)
- **What:** State legislative bills, votes, and session activity for all 50 states
- **API:** `GET https://v3.openstates.org/bills?jurisdiction={state}&updated_since={date}`
- **Auth:** `OPEN_STATES_API_KEY` env var (free tier available)
- **Sector tagging:** Bill subjects are matched against a keyword dictionary to assign `IndustrySector`
- **Coverage:** All 50 states; legislative track (bills that become law)

#### 2. State Agency RSS Feeds (`fetchers/live/state_rss.py`)
- **What:** Executive agency regulatory notices published to state registers
- **Implementation:** Reads `STATE_AGENCY_RSS_FEEDS` from `state_domains.py`; uses `feedparser`
- **Coverage:** Priority states (CA, NY, TX, FL, IL, MA) for Phase 1; expanded in Phase 2
- **Error handling:** Per-feed try/except; individual feed failure does not block other states

#### 3. Sector Aggregators (`fetchers/live/nasaa.py`, `naic.py`, `csbs.py`)
- **NASAA** — National securities regulators aggregate; covers `financial_services`
- **NAIC** — National insurance regulators aggregate; covers `insurance`
- **CSBS** — Conference of State Bank Supervisors; covers `financial_services`
- Each aggregator pre-groups filings by sector, reducing the mapping burden

#### 4. Federal Register State Filter (existing `fetchers/live/federal_register.py`)
- **What:** Federal Register items tagged with state-specific applicability
- **Implementation:** Add `filter_path=state-filings` query param to existing fetcher
- **Coverage:** All 50 states; federal items with state impact notices

---

### `fetch_filings()` Extension

`backend/app/naturalsentinel/fetchers/base.py`:

```python
def fetch_filings(
    domains: list[RegulatoryDomain] | None = None,
    sectors: list[IndustrySector] | None = None,      # NEW
    state_codes: list[StateCode] | None = None,        # NEW
    jurisdiction: Jurisdiction | None = None,          # NEW — None = both
    since_days: int = 7,
    live: bool = False,
    fetch_full_text: bool = False,
) -> list[RegulatoryFiling]:
```

When `sectors` is provided and `domains` is not, `domains` is auto-expanded from
`SECTOR_TO_FEDERAL_DOMAINS` so that a sector query also pulls relevant federal filings.

A new `_fetch_state_live()` function mirrors the existing `_fetch_live()` pattern — calling
each state fetcher in a try/except block with `logger.warning` fallback, deduplicating
by ID, and normalising to `RegulatoryFiling` with `jurisdiction=STATE`.

### State Filings Use the Same Layer 2 Pipeline

State regulatory filings are not a separate ingestion path — they go through the same
Layer 2 pipeline as user-uploaded documents. The difference is the trigger and source:

```
User uploads a PDF → ingest_document(source.file_path) → Layer 2 → viking://documents/...
Fetcher pulls state filing → IngestFilingSkill(url=filing.source_url) → Layer 2 → viking://state_regulations/...
```

`scan_state_filings` calls `IngestFilingSkill` (which wraps `ingest_document` with `source.url`)
for each new filing before running `AnalyzeFilingSkill`. The ingestion is idempotent — if the
`doc_id` is already in Qdrant (`ns_state_filings`) and OpenViking, it is skipped. Only new filings
trigger the full pipeline (structure extraction → hierarchy build → L0/L1/L2 generation → dual-write).

This means state regulatory filings get the same position-aware chunking, verbatim L2 storage,
and L0/L1 summary generation as contracts and medical records. The citation system in §17 therefore
applies identically to both state filings and user-uploaded documents.

---

### Customer Sector Watch Profiles

A new `SectorWatch` table lets customers persist their monitoring preferences:

```
SectorWatch
  id              UUID PK
  owner_id        UUID FK → user.id (CASCADE DELETE)
  industry_sectors  JSON   list[str]   — IndustrySector values
  state_codes       JSON   list[str]   — StateCode values; empty = all states
  active          BOOL    DEFAULT TRUE
  created_at      TIMESTAMPTZ
```

**API routes** (`backend/app/api/routes/sector_watch.py`):

```
GET    /sector-watch/                → list current user's profiles
POST   /sector-watch/                → create a profile
PUT    /sector-watch/{id}            → update sectors / state list
DELETE /sector-watch/{id}            → remove
GET    /sector-watch/{id}/filings    → live fetch for this profile (?since_days=7)
```

---

### New MCP Tools

Two new tools are added to `backend/app/naturalsentinel/mcp/server.py`:

#### `scan_state_filings`
```
Input:
  state_codes  list[str] | "all"   — StateCode values or "all" for every state
  sectors      list[str]           — IndustrySector values
  since_days   int (default 7)

Processing:
  1. Call fetch_filings(sectors, state_codes, jurisdiction=STATE, live=True)
  2. Run AnalyzeFilingSkill with citation-extraction prompt for each filing
  3. Dual-write: Qdrant (ns_state_filings) + OpenViking (viking://state_regulations/...)
  4. Resolve [CITE:...] markers → populate EvidenceLedgerEntry with line-level citations

Output:
  Grouped summary: { state: { sector: [ { filing, impact, evidence_ledger } ] } }
```

#### `get_sector_regulatory_calendar`
```
Input:
  sector       str              — IndustrySector value
  state_codes  list[str]        — StateCode values
  months_ahead int (default 3)

Processing:
  Query Qdrant ns_state_filings filtered by sector + state_codes,
  extract compliance_deadline from ImpactAssessment, sort chronologically.

Output:
  Chronological list of { deadline, filing_title, state, source_url, viking_uri }
```

The existing `scan_regulatory_filings` tool gains optional `jurisdiction` and `sectors`
parameters to enable cross-jurisdiction queries (e.g., "show me all financial_services
filings — federal and state — in the last 30 days").

---

### OpenViking Directory Structure for State Filings

```
viking://state_regulations/
  └── {state_code}/                  e.g. CA/
      └── {sector}/                  e.g. financial_services/
          └── {doc_id}/              e.g. ca-dfpi-2026-04-11/
              ├── .abstract.md       (L0 — generated summary)
              ├── .overview.md       (L1 — section-level overview)
              ├── metadata.json      (source_url, jurisdiction, state_code, sectors, ...)
              └── {section}/
                  └── {paragraph}/
                      ├── full_text.md   (L2 — verbatim original text)
                      └── metadata.json  (line_start, line_end, char_offset, ...)
```

This hierarchy supports both directory-scoped retrieval ("show me all CA financial_services
filings this month") and global vector search across all states and sectors via Qdrant.

---

### Qdrant Collection for State Filings

A dedicated `ns_state_filings` collection separates state filings from general documents:

| Field | Type | Notes |
|---|---|---|
| vector | float[3072] | text-embedding-3-large of chunk text |
| doc_id | string | unique filing identifier |
| chunk_id | string | `{doc_id}:{section}:{para}:{index}` |
| viking_uri | string | stable OpenViking pointer |
| source_url | string | original filing URL |
| state_code | string | StateCode value |
| sector | string | IndustrySector value |
| jurisdiction | string | always "state" |
| agency | string | issuing agency name |
| line_start | int | line in original source |
| line_end | int | |
| excerpt | string | first 200 chars of chunk |
| published_date | string | ISO 8601 |
| change_type | string | ChangeType value |

Filtered searches: `sector = "financial_services" AND state_code IN ["CA", "NY", "TX"]`
Date-range searches: `published_date >= "2026-01-01"`

---

### Rollout Phases (State Monitoring)

> **Dependency:** Phases 7–10 require Phase 1 (Qdrant + OpenViking integration) to be complete.
> Qdrant collection creation, OpenViking client initialization, and `deps.py` wiring must all be
> in place before any state filing can be ingested or searched.

#### Phase 7: State Data Sources
- Implement `open_states.py`, `state_rss.py`, `nasaa.py`, `naic.py`, `csbs.py`
- Add `StateCode`, `Jurisdiction`, `IndustrySector` enums to models
- Extend `RegulatoryFiling` with jurisdiction fields
- Validate: `fetch_filings(sectors=["financial_services"], state_codes=["CA", "NY"], live=True)` returns results

#### Phase 8: State Storage Pipeline
- Create `ns_state_filings` Qdrant collection
- Add OpenViking `state_regulations/` directory hierarchy to ingestion pipeline
- Dual-write state filings through citation-aware chunking
- Validate: Qdrant contains `CA` + `financial_services` vectors with `line_start`/`line_end` payloads

#### Phase 9: Sector Watch & MCP
- Add `SectorWatch` DB table + API routes
- Add `scan_state_filings` and `get_sector_regulatory_calendar` MCP tools
- Validate: call `scan_state_filings` via Claude Desktop, verify cited `EvidenceLedgerEntry` entries

#### Phase 10: Frontend
- Build `/sector-watch` page with sector + state filter bar and filing table
- Add sidebar entry
- Validate: create a watch profile, confirm live filings appear grouped by state and sector
