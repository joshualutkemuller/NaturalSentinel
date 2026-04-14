"""Document intelligence domain models.

Pure Python dataclasses representing a parsed document's structural
hierarchy — ``DocumentNode`` (one section / article / clause), the
enclosing ``DocumentTree``, and ``DocumentChunk`` (a position-tagged L2
text chunk).

Never persisted directly. Persistent storage lives in
``app.naturalsentinel.memory.pg_models.PgDocument`` (PostgreSQL) and
the ``ns_documents`` Qdrant collection. These dataclasses are the
in-flight representation the pipeline, retrieval, and process engine
pass around.

This was previously split between ``app.naturalsentinel.models``
(``DocumentChunk``) and ``app.naturalsentinel.documents.models``
(``DocumentNode`` + ``DocumentTree``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentNode:
    """A single node in a document's structural hierarchy.

    Each node maps to one viking:// directory, three files
    (.abstract.md / .overview.md / <title>.md for L2), and one or more
    Qdrant points (one per L-level that has been generated).
    """

    # Stable identifier: "{doc_id}:{section_path_slug}:{index}"
    node_id: str

    # Human-readable position ("Article 5 > Section 5.2")
    section_path: str

    # Short slug used in OpenViking directory names ("article-5/section-5-2")
    uri_path: str

    # Node type (article, section, clause, exhibit, schedule, heading, paragraph, etc.)
    node_type: str

    # Section heading / title
    title: str

    # Original verbatim text (L2)
    text: str

    # Character offsets within the source file
    char_offset_start: int = 0
    char_offset_end: int = 0

    # Line numbers in original source (1-indexed)
    line_start: int = 1
    line_end: int = 1

    # PDF page number (None for text/HTML sources)
    page_number: int | None = None

    # Generated summaries (populated during or after ingestion)
    abstract: str = ""  # L0 — one sentence
    overview: str = ""  # L1 — 500-2000 tokens

    # Cross-references to other section paths
    cross_references: list[str] = field(default_factory=list)

    # Child nodes (sub-sections, clauses, etc.)
    children: list[DocumentNode] = field(default_factory=list)

    # Arbitrary metadata (ICD codes, CFR citations, obligation flags, etc.)
    metadata: dict[str, Any] = field(default_factory=dict)

    def word_count(self) -> int:
        return len(self.text.split())

    def all_nodes(self) -> list[DocumentNode]:
        """Depth-first traversal of self + all descendants."""
        result = [self]
        for child in self.children:
            result.extend(child.all_nodes())
        return result


@dataclass
class DocumentTree:
    """Full structural representation of a parsed document."""

    doc_id: str
    title: str
    doc_type: str  # "legal" | "medical" | "compliance" | "generic"
    source_url: str  # Original file URL or local path
    file_name: str
    file_size: int  # bytes
    raw_text: str  # Complete extracted text
    root_nodes: list[DocumentNode] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def all_nodes(self) -> list[DocumentNode]:
        """Flat list of all nodes in the tree (depth-first)."""
        result: list[DocumentNode] = []
        for node in self.root_nodes:
            result.extend(node.all_nodes())
        return result

    def section_count(self) -> int:
        return len(self.all_nodes())


@dataclass
class DocumentChunk:
    """A position-tagged verbatim text chunk from an ingested source document.

    Always represents L2 content (original source text, never summarised).
    L0/L1 tiers are generated *from* chunks by the VLM pipeline after ingestion.
    """

    chunk_id: str  # "{doc_id}:{section_path}:{chunk_index}"
    doc_id: str
    section_path: str  # e.g. "Section 3 > Subsection 2(b)"
    text: str  # verbatim original text
    line_start: int  # 1-indexed line number in the original source file
    line_end: int
    char_offset_start: int  # byte offset from start of source file
    char_offset_end: int
    page_number: int | None = None  # PDF page number; None for HTML/text sources
