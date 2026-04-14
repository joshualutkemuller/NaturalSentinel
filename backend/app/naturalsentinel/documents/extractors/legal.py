"""Legal document structure extractor.

Parses contracts, agreements, and similar legal documents into an
Article → Section hierarchy with optional Exhibit/Schedule attachments,
and attaches cross-reference metadata where ``§`` / ``Article`` /
``Section`` citations appear in the text.

Split out of ``extractors.py`` in Phase R.
"""

from __future__ import annotations

import re

from app.naturalsentinel.documents.extractors._common import (
    line_numbers,
    make_node,
    slugify,
)
from app.naturalsentinel.domain.document import DocumentNode

_LEGAL_ARTICLE = re.compile(
    r"(?m)^(ARTICLE\s+[IVXLCDM\d]+[.:—–-]?\s*.{0,80})$",
    re.IGNORECASE,
)
_LEGAL_SECTION = re.compile(
    r"(?m)^(Section\s+[\d.]+\.?\s*.{0,80})$|^(§\s*[\d.]+\s*.{0,80})$",
    re.IGNORECASE,
)
_EXHIBIT = re.compile(
    r"(?m)^(EXHIBIT\s+[A-Z0-9]+[.:—–-]?\s*.{0,80})$|"
    r"^(SCHEDULE\s+[A-Z0-9]+[.:—–-]?\s*.{0,80})$",
    re.IGNORECASE,
)


def extract_legal(raw_text: str, doc_id: str) -> list[DocumentNode]:
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
        slug = slugify(heading)
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
            sub_slug = slugify(sheading)
            sub_uri = f"{uri_path}/section-{sidx + 1}--{sub_slug}"
            sub_path = f"{section_path} > {sheading}"
            ls, le = line_numbers(raw_text, pos + spos)
            sub_nodes.append(
                make_node(
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

        ls, le = line_numbers(raw_text, pos)
        node = make_node(
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
    _attach_cross_references(nodes)
    return nodes


def _attach_cross_references(nodes: list[DocumentNode]) -> None:
    """Add cross-reference metadata to nodes where §/Article references appear.

    Scans each node's own text for legal reference patterns. Originally
    this also took a ``full_text`` argument but never used it; dropped
    in Phase R.
    """
    xref_pattern = re.compile(
        r"(§\s*[\d.]+|Article\s+[IVXLCDM\d]+|Section\s+[\d.]+)", re.IGNORECASE
    )
    for node in nodes:
        refs = list({m.group(0) for m in xref_pattern.finditer(node.text)})
        if refs:
            node.cross_references = refs[:20]  # cap at 20
