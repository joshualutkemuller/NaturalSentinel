"""Generic document structure extractor.

Used as a fallback for arbitrary documents without a recognized legal /
medical / compliance shape. Parses markdown headings and ALL-CAPS
header lines, filtering out lines that are too short or too long to
plausibly be headings. If no headings are found, the entire document
becomes a single node.

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

_HEADING_PATTERN = re.compile(r"(?m)^(#{1,4}\s+.+|[A-Z][A-Z\s]{4,60})\s*$")


def extract_generic(raw_text: str, doc_id: str) -> list[DocumentNode]:
    """Generic structure extraction using markdown headings and ALL CAPS lines."""
    matches = list(_HEADING_PATTERN.finditer(raw_text))

    if not matches:
        # No headings found: treat entire document as one node
        return [
            make_node(
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
        slug = slugify(heading)
        uri_path = f"section-{idx + 1}--{slug}"
        ls, le = line_numbers(raw_text, pos)
        nodes.append(
            make_node(
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
