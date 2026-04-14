"""Document structure extractors.

Each extractor takes raw text (already extracted from the source file) and
returns a :class:`DocumentTree` with a populated section hierarchy.

Extractors are pattern-based for speed and reliability. They do not call
an LLM — LLM summarization happens in the ingestion pipeline (Stage 5).

Usage::

    from app.naturalsentinel.documents.extractors import extract_structure

    tree = extract_structure(
        raw_text="ARTICLE 1\\nDEFINITIONS\\n...",
        doc_id="uuid-...",
        doc_type="legal",
        source_url="file:///path/to/agreement.pdf",
        file_name="agreement.pdf",
        file_size=102400,
    )
"""

from __future__ import annotations

import re
from typing import Any

from app.naturalsentinel.documents.models import DocumentNode, DocumentTree

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

    extractors = {
        "legal": _extract_legal,
        "medical": _extract_medical,
        "compliance": _extract_compliance,
        "generic": _extract_generic,
    }
    extractor_fn = extractors.get(effective_type, _extract_generic)
    root_nodes = extractor_fn(raw_text, doc_id)

    # Fall back to generic if the domain extractor found nothing
    if not root_nodes:
        root_nodes = _extract_generic(raw_text, doc_id)

    # Extract title from first heading or first line
    title = _extract_title(raw_text, file_name)

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


def _extract_title(text: str, file_name: str) -> str:
    """Extract document title from first heading or filename."""
    for line in text.splitlines()[:20]:
        line = line.strip()
        if len(line) > 5 and len(line) < 200 and not line.startswith("#"):
            # Skip lines that look like pure body text (>80 chars or contain lowercase midsentence)
            if len(line) < 100 and (
                line.isupper()
                or line.istitle()
                or line.startswith("AGREEMENT")
                or line.startswith("CONTRACT")
            ):
                return line
        if line.startswith("#"):
            return line.lstrip("#").strip()
    # Fall back to filename without extension
    return (
        re.sub(r"\.[a-zA-Z]{2,5}$", "", file_name)
        .replace("_", " ")
        .replace("-", " ")
        .title()
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node(
    doc_id: str,
    index: int,
    title: str,
    text: str,
    node_type: str,
    section_path: str,
    uri_path: str,
    char_start: int,
    char_end: int,
    line_start: int,
    line_end: int,
    metadata: dict | None = None,
) -> DocumentNode:
    node_id = f"{doc_id}:{uri_path}:{index}"
    abstract = _first_sentence(text)
    overview = text[:1500].strip() if len(text) > 50 else text
    return DocumentNode(
        node_id=node_id,
        section_path=section_path,
        uri_path=uri_path,
        node_type=node_type,
        title=title,
        text=text,
        char_offset_start=char_start,
        char_offset_end=char_end,
        line_start=line_start,
        line_end=line_end,
        abstract=abstract,
        overview=overview,
        metadata=metadata or {},
    )


def _first_sentence(text: str) -> str:
    """Return the first sentence (up to 200 chars) of text."""
    text = text.strip()
    for sep in (".", "!", "?"):
        pos = text.find(sep)
        if 10 < pos < 200:
            return text[: pos + 1].strip()
    return text[:200].rstrip() + ("…" if len(text) > 200 else "")


def _slugify(text: str) -> str:
    """Convert a heading to a safe URI path component."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    return slug[:60].strip("-") or "section"


def _line_numbers(text: str, start_char: int) -> tuple[int, int]:
    """Return (line_start, line_end) for a substring starting at start_char."""
    prefix = text[:start_char]
    line_start = prefix.count("\n") + 1
    content_lines = text[start_char:].count("\n")
    return line_start, line_start + content_lines


# ---------------------------------------------------------------------------
# Legal extractor
# ---------------------------------------------------------------------------

_LEGAL_ARTICLE = re.compile(
    r"(?m)^(ARTICLE\s+[IVXLCDM\d]+[.:—–-]?\s*.{0,80})$",
    re.IGNORECASE,
)
_LEGAL_SECTION = re.compile(
    r"(?m)^(Section\s+[\d.]+\.?\s*.{0,80})$|^(§\s*[\d.]+\s*.{0,80})$",
    re.IGNORECASE,
)
_EXHIBIT = re.compile(
    r"(?m)^(EXHIBIT\s+[A-Z0-9]+[.:—–-]?\s*.{0,80})$|^(SCHEDULE\s+[A-Z0-9]+[.:—–-]?\s*.{0,80})$",
    re.IGNORECASE,
)


def _extract_legal(raw_text: str, doc_id: str) -> list[DocumentNode]:
    """Extract legal document structure: articles → sections, with exhibits."""
    # Split at article and exhibit boundaries
    boundaries: list[tuple[int, str, str]] = []  # (char_pos, node_type, heading)

    for m in _LEGAL_ARTICLE.finditer(raw_text):
        boundaries.append((m.start(), "article", m.group(0).strip()))
    for m in _EXHIBIT.finditer(raw_text):
        boundaries.append((m.start(), "exhibit", m.group(0).strip()))

    boundaries.sort(key=lambda x: x[0])

    if not boundaries:
        # Fall back: no article structure found
        return []

    nodes: list[DocumentNode] = []
    for idx, (pos, ntype, heading) in enumerate(boundaries):
        end_pos = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else len(raw_text)
        chunk = raw_text[pos:end_pos]
        slug = _slugify(heading)
        art_num = idx + 1
        uri_path = f"{ntype}-{art_num}--{slug}"
        section_path = heading

        # Find sub-sections within this article
        sub_nodes: list[DocumentNode] = []
        sub_boundaries: list[tuple[int, str, str]] = []
        for sm in _LEGAL_SECTION.finditer(chunk):
            sub_boundaries.append((sm.start(), "section", sm.group(0).strip()))

        for sidx, (spos, _, sheading) in enumerate(sub_boundaries):
            send = (
                sub_boundaries[sidx + 1][0]
                if sidx + 1 < len(sub_boundaries)
                else len(chunk)
            )
            sub_text = chunk[spos:send]
            sub_slug = _slugify(sheading)
            sub_uri = f"{uri_path}/section-{sidx + 1}--{sub_slug}"
            sub_path = f"{section_path} > {sheading}"
            ls, le = _line_numbers(raw_text, pos + spos)
            sub_nodes.append(
                _make_node(
                    doc_id,
                    sidx,
                    sheading,
                    sub_text,
                    "section",
                    sub_path,
                    sub_uri,
                    pos + spos,
                    pos + send,
                    ls,
                    le,
                )
            )

        ls, le = _line_numbers(raw_text, pos)
        node = _make_node(
            doc_id,
            idx,
            heading,
            chunk,
            ntype,
            section_path,
            uri_path,
            pos,
            end_pos,
            ls,
            le,
        )
        node.children = sub_nodes
        nodes.append(node)

    # Detect cross-references
    _attach_cross_references(nodes, raw_text)
    return nodes


def _attach_cross_references(nodes: list[DocumentNode], full_text: str) -> None:
    """Add cross-reference metadata to nodes where §/Article references appear."""
    xref_pattern = re.compile(
        r"(§\s*[\d.]+|Article\s+[IVXLCDM\d]+|Section\s+[\d.]+)", re.IGNORECASE
    )
    for node in nodes:
        refs = list({m.group(0) for m in xref_pattern.finditer(node.text)})
        if refs:
            node.cross_references = refs[:20]  # cap at 20


# ---------------------------------------------------------------------------
# Medical extractor
# ---------------------------------------------------------------------------

_MEDICAL_SECTIONS = [
    "CHIEF COMPLAINT",
    "HISTORY OF PRESENT ILLNESS",
    "HPI",
    "PAST MEDICAL HISTORY",
    "PMH",
    "MEDICATIONS",
    "ALLERGIES",
    "REVIEW OF SYSTEMS",
    "ROS",
    "PHYSICAL EXAMINATION",
    "VITAL SIGNS",
    "ASSESSMENT",
    "DIAGNOSIS",
    "PLAN",
    "ORDERS",
    "LABS",
    "RADIOLOGY",
    "PROCEDURES",
    "DISCHARGE SUMMARY",
    "FOLLOW-UP",
    "NOTES",
]
_MEDICAL_PATTERN = re.compile(
    r"(?mi)^(" + "|".join(re.escape(s) for s in _MEDICAL_SECTIONS) + r")[:\s]*$",
)


def _extract_medical(raw_text: str, doc_id: str) -> list[DocumentNode]:
    """Extract medical document structure: SOAP + standard sections."""
    matches = list(_MEDICAL_PATTERN.finditer(raw_text))
    if not matches:
        return []

    nodes: list[DocumentNode] = []
    for idx, m in enumerate(matches):
        pos = m.start()
        end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw_text)
        heading = m.group(0).strip().upper().rstrip(":")
        text = raw_text[pos:end_pos]
        slug = _slugify(heading)
        uri_path = f"section-{idx + 1}--{slug}"
        ls, le = _line_numbers(raw_text, pos)

        # Extract ICD/CPT codes
        meta: dict = {}
        icd_codes = re.findall(r"\b[A-Z]\d{2}(?:\.\d+)?\b", text)
        if icd_codes:
            meta["icd_codes"] = list(set(icd_codes[:20]))
        cpt_codes = re.findall(r"\b\d{5}[A-Z]?\b", text)
        if cpt_codes:
            meta["cpt_codes"] = list(set(cpt_codes[:20]))

        nodes.append(
            _make_node(
                doc_id,
                idx,
                heading,
                text,
                "medical_section",
                heading,
                uri_path,
                pos,
                end_pos,
                ls,
                le,
                meta,
            )
        )
    return nodes


# ---------------------------------------------------------------------------
# Compliance extractor
# ---------------------------------------------------------------------------

_OBLIGATION_WORDS = re.compile(
    r"\b(shall|must|required to|is required|are required|will be required|obligated to)\b",
    re.IGNORECASE,
)
_DATE_PATTERN = re.compile(
    r"\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b"
)
_CFR_PATTERN = re.compile(r"\b\d+\s+CFR\s+(?:§\s*)?\d+(?:\.\d+)*\b")
_USC_PATTERN = re.compile(r"\b\d+\s+U\.S\.C\.?\s+§\s*\d+\b")
_FR_PATTERN = re.compile(r"\b\d{2,3}\s+Fed\.\s*Reg\.\s*\d+\b", re.IGNORECASE)


def _extract_compliance(raw_text: str, doc_id: str) -> list[DocumentNode]:
    """Extract compliance document structure.

    Compliance docs are often structured similarly to legal docs but with
    explicit obligation markers and regulatory citations.
    """
    # Try legal extraction first as fallback skeleton
    base_nodes = _extract_legal(raw_text, doc_id)
    if not base_nodes:
        base_nodes = _extract_generic(raw_text, doc_id)

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


# ---------------------------------------------------------------------------
# Generic extractor (heading-based)
# ---------------------------------------------------------------------------

_HEADING_PATTERN = re.compile(r"(?m)^(#{1,4}\s+.+|[A-Z][A-Z\s]{4,60})\s*$")


def _extract_generic(raw_text: str, doc_id: str) -> list[DocumentNode]:
    """Generic structure extraction using markdown headings and ALL CAPS lines."""
    matches = list(_HEADING_PATTERN.finditer(raw_text))

    if not matches:
        # No headings found: treat entire document as one node
        return [
            _make_node(
                doc_id,
                0,
                "Document",
                raw_text,
                "document",
                "Document",
                "document",
                0,
                len(raw_text),
                1,
                raw_text.count("\n") + 1,
            )
        ]

    # Filter to likely headings (not just any uppercase line)
    filtered: list[re.Match] = []
    for m in matches:
        heading = m.group(0).strip()
        # Skip very short or very long headings
        if 3 < len(heading) < 100:
            filtered.append(m)

    if not filtered:
        return []

    nodes: list[DocumentNode] = []
    for idx, m in enumerate(filtered):
        pos = m.start()
        end_pos = (
            filtered[idx + 1].start() if idx + 1 < len(filtered) else len(raw_text)
        )
        heading = m.group(0).strip().lstrip("#").strip()
        text = raw_text[pos:end_pos]
        slug = _slugify(heading)
        uri_path = f"section-{idx + 1}--{slug}"
        ls, le = _line_numbers(raw_text, pos)
        nodes.append(
            _make_node(
                doc_id,
                idx,
                heading,
                text,
                "section",
                heading,
                uri_path,
                pos,
                end_pos,
                ls,
                le,
            )
        )
    return nodes
