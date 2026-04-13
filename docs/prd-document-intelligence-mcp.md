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
| Existing MCP server (`mcp/server.py`) | Remains as-is for regulatory monitoring tools (`scan_regulatory_filings`, `analyze_filing_text`, etc.). The new document MCP server is a separate server that can run alongside it or be merged later. |
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
  "file_path": "string (required) — absolute path to the document file",
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
  "doc_ids": ["string (optional) — scope to specific documents. Empty = search all."],
  "token_budget": "int (optional, default 4096) — max tokens in returned context",
  "depth": "'abstract' | 'overview' | 'detail' (optional, default 'overview') — maximum L-level to return",
  "include_cross_references": "boolean (optional, default true) — follow document cross-references"
}
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
│        id: deterministic UUID from uri+level │
│        vector: dense embedding               │
│        payload:                              │
│          uri: viking://documents/...         │
│          doc_id: parent document UUID        │
│          section_path: "Art 5 > § 5.2"       │
│          level: 0 | 1 | 2                    │
│          doc_type: "legal"                   │
│          node_type: "section" | "clause" ... │
│          title: section heading              │
│          abstract: L0 text                   │
│          created_at: ISO timestamp           │
│          tags: from document metadata        │
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
  uri:            keyword    — viking:// URI for this section+level
  doc_id:         keyword    — parent document UUID
  section_path:   text       — human-readable path ("Article 5 > Section 5.2")
  level:          integer    — 0 (L0), 1 (L1), 2 (L2)
  doc_type:       keyword    — "legal", "medical", "compliance", "generic"
  node_type:      keyword    — "article", "section", "clause", "exhibit", etc.
  title:          text       — section heading
  abstract:       text       — L0 text (always populated)
  created_at:     datetime   — ingestion timestamp
  tags:           keyword[]  — from document metadata
  word_count:     integer    — token estimate for budget planning
```

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

**Token budget comparison:**
| Approach | Tokens consumed |
|---|---|
| Full document in context | ~80,000 |
| Traditional RAG (top-10 chunks) | ~20,000 |
| This system (L0 scan → L1 for 10 → L2 for 2) | ~5,500 |

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
          │ Budget: 4096 tokens     │
          │                         │
          │ Step 1: Load all L0s    │
          │   25 × ~100 = 2,500 t  │
          │                         │
          │ Step 2: Remaining budget│
          │   4096 - 2500 = 1,596 t │
          │                         │
          │ Step 3: Promote top     │
          │   candidates to L1      │
          │   ~1,000 t each         │
          │   Promote top 1-2       │
          │                         │
          │ Step 4: If still budget,│
          │   note L2 available for │
          │   agent to request      │
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
OPENVIKING_VLM_MODEL: str = "claude-sonnet-4-6-20250514"
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

Tracks ingested documents at the relational level. Complements the OpenViking filesystem representation.

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
| `OPENVIKING_VLM_MODEL` | `claude-sonnet-4-6-20250514` | VLM model name |
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
