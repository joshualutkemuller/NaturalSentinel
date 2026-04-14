"""Shared helpers for the document structure extractors.

These are private to the ``extractors`` package — they're consumed by
the per-type extractor modules (legal, medical, compliance, generic)
but are not part of the public API.

This file was split out of ``extractors.py`` in Phase R so each
document type's extractor lives in its own file.
"""

from __future__ import annotations

import re

from app.naturalsentinel.domain.document import DocumentNode


def extract_title(text: str, file_name: str) -> str:
    """Extract document title from first heading or filename."""
    for line in text.splitlines()[:20]:
        line = line.strip()
        if len(line) > 5 and len(line) < 200 and not line.startswith("#"):
            # Skip lines that look like pure body text
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


def make_node(
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
    """Build a DocumentNode with a stable node_id + derived L0/L1."""
    node_id = f"{doc_id}:{uri_path}:{index}"
    abstract = first_sentence(text)
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


def first_sentence(text: str) -> str:
    """Return the first sentence (up to 200 chars) of text."""
    text = text.strip()
    for sep in (".", "!", "?"):
        pos = text.find(sep)
        if 10 < pos < 200:
            return text[: pos + 1].strip()
    return text[:200].rstrip() + ("…" if len(text) > 200 else "")


def slugify(text: str) -> str:
    """Convert a heading to a safe URI path component."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    return slug[:60].strip("-") or "section"


def line_numbers(text: str, start_char: int) -> tuple[int, int]:
    """Return (line_start, line_end) for a substring starting at start_char."""
    prefix = text[:start_char]
    line_start = prefix.count("\n") + 1
    content_lines = text[start_char:].count("\n")
    return line_start, line_start + content_lines
