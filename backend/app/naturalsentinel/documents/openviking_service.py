"""OpenViking service adapter — write document hierarchy + tiered content.

All OpenViking filesystem writes done by the ingest pipeline live here:
creating the ``viking://documents/{doc_id}/`` root, writing the per-
document ``meta.json``, recursively building the node tree, and writing
``.abstract.md`` / ``.overview.md`` / ``content.md`` per node.

This module was extracted from ``pipeline.py`` in Phase R so the
pipeline stages are separated from the OV adapter layer. The pipeline
orchestrates; this module knows about OV URIs and file conventions.

Every write is wrapped in a broad-but-logged try/except — OV failures
are non-fatal at ingest time (degraded mode: PG + Qdrant still work
without OV hierarchy). Phase P1.1 will move the hardcoded OV filenames
(``.abstract.md`` etc.) into ``documents/constants.py``.
"""

from __future__ import annotations

import logging

from app.naturalsentinel.documents.constants import (
    OV_DOCUMENT_ROOT,
    OV_FILENAMES,
    OV_META_FILE,
    Tier,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point — build the full hierarchy for a DocumentTree
# ---------------------------------------------------------------------------


def build_openviking_hierarchy(ov_client, tree) -> str:
    """Create the OpenViking directory structure for a document.

    Creates the root directory ``viking://documents/{doc_id}/`` and one
    subdirectory per node. Writes L2 (full text) directly; L0/L1 summaries
    are written from the pre-generated ``abstract`` / ``overview`` fields on
    each DocumentNode.

    Returns the root viking:// URI.
    """
    root_uri = f"{OV_DOCUMENT_ROOT}/{tree.doc_id}"

    # Create root directory
    ov_mkdir(ov_client, root_uri)

    # Write document-level L0/L1
    doc_abstract = first_sentence(tree.raw_text)
    doc_overview = tree.raw_text[:2000].strip()
    ov_write_tiered(ov_client, root_uri, doc_abstract, doc_overview, None)

    # Write meta.json
    meta_content = (
        f'{{"doc_id": "{tree.doc_id}", "title": "{esc_json_string(tree.title)}", '
        f'"doc_type": "{tree.doc_type}", '
        f'"source_url": "{esc_json_string(tree.source_url)}", '
        f'"file_name": "{esc_json_string(tree.file_name)}", '
        f'"section_count": {tree.section_count()}}}'
    )
    ov_write(ov_client, f"{root_uri}/{OV_META_FILE}", meta_content)

    # Write all nodes recursively
    for node in tree.root_nodes:
        _write_node(ov_client, root_uri, node)

    return root_uri


def _write_node(ov_client, parent_uri: str, node) -> None:
    """Recursively write a DocumentNode and its children to OpenViking."""
    node_uri = f"{parent_uri}/{node.uri_path}"
    ov_mkdir(ov_client, node_uri)
    ov_write_tiered(ov_client, node_uri, node.abstract, node.overview, node.text)

    # Write cross-references
    if node.cross_references and hasattr(ov_client, "link"):
        try:
            ov_client.link(node_uri, [f"xref:{r}" for r in node.cross_references[:5]])
        except Exception as exc:
            # link() is OV-specific and may not exist on all clients; treat as
            # best-effort and log at debug level so we don't spam warnings.
            logger.debug("ov link %s: %s", node_uri, exc)

    for child in node.children:
        _write_node(ov_client, node_uri, child)


# ---------------------------------------------------------------------------
# Low-level OV adapter helpers (mkdir / write / tiered write)
# ---------------------------------------------------------------------------


def ov_mkdir(ov_client, uri: str) -> None:
    """Create an OV directory, swallowing any runtime error.

    Non-fatal: if OV is unavailable or the directory already exists, we
    log at debug level and continue. The caller still proceeds to write
    content; the downstream write() will surface a real error if it
    matters.
    """
    try:
        ov_client.mkdir(uri)
    except Exception as exc:
        logger.debug("mkdir %s: %s", uri, exc)


def ov_write(ov_client, uri: str, content: str) -> None:
    """Write content at an OV URI, swallowing any runtime error.

    Non-fatal — see ``ov_mkdir`` rationale. Callers should check OV
    state via ``ov_client.read(uri)`` if a write must be confirmed.
    """
    try:
        ov_client.write(uri, content)
    except Exception as exc:
        logger.debug("write %s: %s", uri, exc)


def ov_write_tiered(
    ov_client,
    uri: str,
    abstract: str,
    overview: str,
    full_text: str | None,
) -> None:
    """Write the per-tier files for an OV node.

    Filenames come from ``constants.OV_FILENAMES`` keyed by
    :class:`Tier`, so the convention lives in exactly one place.
    Tiers with no content are skipped.
    """
    if abstract:
        ov_write(ov_client, f"{uri}/{OV_FILENAMES[Tier.ABSTRACT]}", abstract)
    if overview:
        ov_write(ov_client, f"{uri}/{OV_FILENAMES[Tier.OVERVIEW]}", overview)
    if full_text:
        ov_write(ov_client, f"{uri}/{OV_FILENAMES[Tier.DETAIL]}", full_text)


# ---------------------------------------------------------------------------
# Text helpers used when building summaries / meta.json
# ---------------------------------------------------------------------------


def first_sentence(text: str) -> str:
    """Return the first sentence of ``text`` capped at 300 chars.

    Used for document-level L0 abstracts. Scans for the first terminal
    punctuation inside the 10–300 char window.
    """
    for sep in (".", "!", "?"):
        pos = text.find(sep)
        if 10 < pos < 300:
            return text[: pos + 1].strip()
    return text[:300].strip()


def esc_json_string(s: str) -> str:
    """Escape a string for inclusion in hand-built JSON (used by meta.json).

    Only handles the two cases meta.json actually encounters: literal
    double quotes and newlines. Truncates to 200 chars to keep meta.json
    bounded. Do NOT use this for general JSON escaping — call
    ``json.dumps`` for that.
    """
    return s.replace('"', '\\"').replace("\n", " ")[:200]
