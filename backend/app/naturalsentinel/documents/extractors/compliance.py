"""Compliance document structure extractor.

Compliance docs (regulatory guidance, rules, policy statements) are
typically shaped like legal documents but with explicit obligation
markers ("shall", "must"), effective dates, and statutory / regulatory
citations (CFR, USC, Federal Register). This extractor delegates
structural parsing to the legal extractor (with generic as a fallback)
and overlays compliance-specific metadata on every node.

Split out of ``extractors.py`` in Phase R.
"""

from __future__ import annotations

import re

from app.naturalsentinel.documents.extractors.generic import extract_generic
from app.naturalsentinel.documents.extractors.legal import extract_legal
from app.naturalsentinel.domain.document import DocumentNode

_OBLIGATION_WORDS = re.compile(
    r"\b(shall|must|required to|is required|are required|will be required|obligated to)\b",
    re.IGNORECASE,
)
_DATE_PATTERN = re.compile(
    r"\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|"
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},?\s+\d{4})\b"
)
_CFR_PATTERN = re.compile(r"\b\d+\s+CFR\s+(?:§\s*)?\d+(?:\.\d+)*\b")
_USC_PATTERN = re.compile(r"\b\d+\s+U\.S\.C\.?\s+§\s*\d+\b")
_FR_PATTERN = re.compile(r"\b\d{2,3}\s+Fed\.\s*Reg\.\s*\d+\b", re.IGNORECASE)


def extract_compliance(raw_text: str, doc_id: str) -> list[DocumentNode]:
    """Extract compliance document structure.

    Compliance docs are often structured similarly to legal docs but with
    explicit obligation markers and regulatory citations. This extractor
    uses the legal extractor for the skeletal hierarchy and overlays
    per-node compliance metadata (obligation count, effective dates,
    CFR/USC/FR citations).
    """
    # Try legal extraction first as fallback skeleton
    base_nodes = extract_legal(raw_text, doc_id)
    if not base_nodes:
        base_nodes = extract_generic(raw_text, doc_id)

    # Annotate each node with compliance metadata
    for node in base_nodes:
        for n in [node] + node.children:
            obls = len(_OBLIGATION_WORDS.findall(n.text))
            dates = _DATE_PATTERN.findall(n.text)
            cfrs = _CFR_PATTERN.findall(n.text)
            uscs = _USC_PATTERN.findall(n.text)
            frs = _FR_PATTERN.findall(n.text)
            n.metadata.update(
                {
                    "obligation_count": obls,
                    "effective_dates": list(set(dates[:10])),
                    "cfr_citations": list(set(cfrs[:10])),
                    "usc_citations": list(set(uscs[:10])),
                    "fr_citations": list(set(frs[:10])),
                }
            )

    return base_nodes
