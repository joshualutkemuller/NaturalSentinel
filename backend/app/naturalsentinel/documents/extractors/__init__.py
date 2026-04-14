"""Document structure extractors.

Each extractor takes raw text (already extracted from the source file) and
returns a :class:`DocumentTree` with a populated section hierarchy.

Extractors are pattern-based for speed and reliability. They do not call
an LLM — LLM summarization happens in the ingestion pipeline (Stage 5).

Phase R split the previous monolithic ``extractors.py`` (~520 lines)
into per-type files plus a shared ``_common.py`` with the helpers every
extractor needs. Public API stays the same::

    from app.naturalsentinel.documents.extractors import extract_structure

    tree = extract_structure(
        raw_text="ARTICLE 1\\nDEFINITIONS\\n...",
        doc_id="uuid-...",
        doc_type="legal",
        source_url="file:///path/to/agreement.pdf",
        file_name="agreement.pdf",
        file_size=102400,
    )

Adding a new document type
--------------------------
Until Phase P2.3 lands ``@register_extractor``, add a new type by:

1. Create a new file in this package (e.g. ``patent.py``) that
   exposes ``extract_patent(raw_text, doc_id) -> list[DocumentNode]``.
2. Add a signal list to ``_infer_doc_type`` so auto-detection works.
3. Add the dispatch entry to the ``EXTRACTORS`` dict below.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.naturalsentinel.documents.extractors._common import extract_title
from app.naturalsentinel.documents.extractors.compliance import extract_compliance
from app.naturalsentinel.documents.extractors.generic import extract_generic
from app.naturalsentinel.documents.extractors.legal import extract_legal
from app.naturalsentinel.documents.extractors.medical import extract_medical
from app.naturalsentinel.domain.document import DocumentNode, DocumentTree

# ---------------------------------------------------------------------------
# Dispatch table — the document-type → extractor registry
# ---------------------------------------------------------------------------

ExtractorFn = Callable[[str, str], list[DocumentNode]]

EXTRACTORS: dict[str, ExtractorFn] = {
    "legal": extract_legal,
    "medical": extract_medical,
    "compliance": extract_compliance,
    "generic": extract_generic,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract_structure(
    raw_text: str,
    doc_id: str,
    doc_type: str,
    source_url: str,
    file_name: str,
    file_size: int,
    metadata: dict[str, Any] | None = None,
) -> DocumentTree:
    """Auto-detect structure and build a DocumentTree.

    Args:
        raw_text: Full extracted text of the document.
        doc_id: UUID string for the parent document.
        doc_type: One of ``"legal"``, ``"medical"``, ``"compliance"``, ``"generic"``.
            When ``"auto"`` is passed, the type is inferred from content signals.
        source_url: Original URL or file path.
        file_name: Base filename (for display).
        file_size: Byte size of the original file.
        metadata: Optional extra metadata dict.

    Returns:
        A populated :class:`DocumentTree`.
    """
    effective_type = doc_type if doc_type != "auto" else _infer_doc_type(raw_text)

    extractor_fn = EXTRACTORS.get(effective_type, extract_generic)
    root_nodes = extractor_fn(raw_text, doc_id)

    # Fall back to generic if the domain extractor found nothing
    if not root_nodes:
        root_nodes = extract_generic(raw_text, doc_id)

    title = extract_title(raw_text, file_name)

    return DocumentTree(
        doc_id=doc_id,
        title=title,
        doc_type=effective_type,
        source_url=source_url,
        file_name=file_name,
        file_size=file_size,
        raw_text=raw_text,
        root_nodes=root_nodes,
        metadata=metadata or {},
    )


def _infer_doc_type(text: str) -> str:
    """Heuristically determine document type from content signals."""
    sample = text[:3000].lower()
    legal_signals = [
        "agreement",
        "shall",
        "party",
        "recitals",
        "article",
        "section",
        "whereas",
        "exhibit",
    ]
    medical_signals = [
        "patient",
        "diagnosis",
        "treatment",
        "medication",
        "physician",
        "icd",
        "chief complaint",
        "assessment",
    ]
    compliance_signals = [
        "regulation",
        "pursuant",
        "shall comply",
        "cfr",
        "federal register",
        "effective date",
        "rule",
    ]

    scores = {
        "legal": sum(1 for s in legal_signals if s in sample),
        "medical": sum(1 for s in medical_signals if s in sample),
        "compliance": sum(1 for s in compliance_signals if s in sample),
    }
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] >= 2 else "generic"


__all__ = [
    "EXTRACTORS",
    "extract_compliance",
    "extract_generic",
    "extract_legal",
    "extract_medical",
    "extract_structure",
]
