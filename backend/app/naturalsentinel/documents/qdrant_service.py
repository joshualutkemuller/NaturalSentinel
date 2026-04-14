"""Qdrant service for document embeddings.

Manages the ``ns_documents`` and ``ns_state_filings`` collections. Provides:
- Collection creation (idempotent)
- Point upsert (document section + state filing embeddings)
- Semantic search with payload filtering

The embedding model is a no-op (returns zero vectors) when no real embedding
provider is configured. In production, ``OPENAI_API_KEY`` enables real
``text-embedding-3-large`` (3072-dim) vectors via the configured provider.
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EMBEDDING_DIM = 3072
_NS_DOCUMENTS = "ns_documents"
_NS_STATE_FILINGS = "ns_state_filings"
_NS_SESSIONS = "ns_sessions"


# ---------------------------------------------------------------------------
# Collection management
# ---------------------------------------------------------------------------


def ensure_collections(client) -> None:
    """Create required collections if they don't already exist.

    Called once at server startup. Safe to call multiple times.

    Top-level ``ImportError`` (qdrant-client not installed at all) is
    tolerated — the rest of the app keeps working without vector
    search. Any other import failure (renamed/removed classes) bubbles
    up so we crash boot instead of silently losing functionality.
    """
    try:
        from qdrant_client.http.models import Distance, VectorParams
    except ImportError:
        logger.warning("qdrant-client not installed; skipping collection setup")
        return

    existing = {c.name for c in client.get_collections().collections}

    for collection_name in (_NS_DOCUMENTS, _NS_STATE_FILINGS, _NS_SESSIONS):
        if collection_name in existing:
            continue
        try:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=_EMBEDDING_DIM, distance=Distance.COSINE
                ),
            )
            logger.info("Created Qdrant collection: %s", collection_name)
        except Exception as exc:
            # Transient network / RPC failures — log and keep going so
            # the other collections still get created.
            logger.warning("Could not create collection %s: %s", collection_name, exc)


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------


def embed_text(text: str) -> list[float]:
    """Generate a dense embedding for text.

    Uses OpenAI text-embedding-3-large when ``OPENAI_API_KEY`` is set,
    otherwise returns a deterministic zero vector (usable for testing /
    mock mode — search will return results in insertion order).
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        # Deterministic mock: hash-based pseudo-embedding (for dev/testing).
        # Expand to 3072 floats using structured per-chunk hashing of the input.
        values: list[float] = []
        for i in range(0, _EMBEDDING_DIM, 32):
            chunk_hash = hashlib.sha256(f"{i}:{text[:100]}".encode()).digest()
            for b in chunk_hash:
                values.append((b - 127.5) / 127.5)
        return values[:_EMBEDDING_DIM]

    try:
        import httpx

        resp = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"model": "text-embedding-3-large", "input": text[:8000]},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]
    except Exception as exc:
        logger.warning("Embedding API call failed, using zero vector: %s", exc)
        return [0.0] * _EMBEDDING_DIM


# ---------------------------------------------------------------------------
# Point helpers
# ---------------------------------------------------------------------------


def _stable_point_id(chunk_id: str, level: int) -> str:
    """Generate a deterministic UUID for a Qdrant point."""
    return str(uuid.UUID(hashlib.md5(f"{chunk_id}:{level}".encode()).hexdigest()))


# ---------------------------------------------------------------------------
# Document section upsert
# ---------------------------------------------------------------------------


def upsert_document_sections(
    client,
    doc_id: str,
    doc_type: str,
    source_url: str,
    tags: list[str],
    sections: list[dict],
) -> int:
    """Upsert embeddings for all sections of a document.

    Each section dict must contain:
        chunk_id, viking_uri, section_path, node_type, title, text,
        abstract, overview, line_start, line_end, char_offset_start,
        char_offset_end, page_number (optional), word_count

    Returns the number of points upserted.

    Tolerates qdrant-client missing entirely (returns 0 with a warning)
    but re-raises any structural import error from inside the package.
    """
    try:
        import qdrant_client  # noqa: F401  — availability probe
    except ImportError:
        logger.warning("qdrant-client not installed; skipping section upsert")
        return 0
    from qdrant_client.http.models import PointStruct

    points: list[Any] = []

    for sec in sections:
        chunk_id = sec["chunk_id"]
        viking_uri = sec["viking_uri"]
        title = sec.get("title", "")
        abstract_text = sec.get("abstract", "")
        overview_text = sec.get("overview", "")
        l2_text = sec.get("text", "")

        # L0 point (abstract)
        if abstract_text:
            points.append(
                PointStruct(
                    id=_stable_point_id(chunk_id, 0),
                    vector=embed_text(abstract_text),
                    payload={
                        "viking_uri": viking_uri,
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "source_url": source_url,
                        "section_path": sec["section_path"],
                        "level": 0,
                        "doc_type": doc_type,
                        "node_type": sec.get("node_type", "section"),
                        "title": title,
                        "abstract": abstract_text,
                        "tags": tags,
                        "word_count": sec.get("word_count", 0),
                    },
                )
            )

        # L1 point (overview)
        if overview_text:
            points.append(
                PointStruct(
                    id=_stable_point_id(chunk_id, 1),
                    vector=embed_text(overview_text),
                    payload={
                        "viking_uri": viking_uri,
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "source_url": source_url,
                        "section_path": sec["section_path"],
                        "level": 1,
                        "doc_type": doc_type,
                        "node_type": sec.get("node_type", "section"),
                        "title": title,
                        "abstract": abstract_text,
                        "tags": tags,
                        "word_count": sec.get("word_count", 0),
                    },
                )
            )

        # L2 point (full section text + citation fields)
        if l2_text:
            points.append(
                PointStruct(
                    id=_stable_point_id(chunk_id, 2),
                    vector=embed_text(l2_text),
                    payload={
                        "viking_uri": viking_uri,
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "source_url": source_url,
                        "section_path": sec["section_path"],
                        "level": 2,
                        "doc_type": doc_type,
                        "node_type": sec.get("node_type", "section"),
                        "title": title,
                        "abstract": abstract_text,
                        "excerpt": l2_text[:200],
                        "line_start": sec.get("line_start"),
                        "line_end": sec.get("line_end"),
                        "char_offset_start": sec.get("char_offset_start"),
                        "char_offset_end": sec.get("char_offset_end"),
                        "page_number": sec.get("page_number"),
                        "tags": tags,
                        "word_count": sec.get("word_count", 0),
                    },
                )
            )

    if not points:
        return 0

    # Batch upsert in chunks of 100
    batch_size = 100
    total = 0
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        try:
            client.upsert(collection_name=_NS_DOCUMENTS, points=batch)
            total += len(batch)
        except Exception as exc:
            logger.warning(
                "Qdrant upsert failed for batch %d: %s", i // batch_size, exc
            )

    return total


# ---------------------------------------------------------------------------
# State filing upsert
# ---------------------------------------------------------------------------


def upsert_state_filing(client, filing_dict: dict) -> bool:
    """Upsert a single state regulatory filing into ns_state_filings.

    filing_dict must contain: filing_id, title, state_code, sector,
    agency, jurisdiction, source_url, published_date, change_type,
    raw_text (for embedding).

    Tolerates ``qdrant-client`` not being installed (returns False). A
    missing ``PointStruct`` class is a structural error and bubbles up.
    """
    try:
        import qdrant_client  # noqa: F401  — probe only
    except ImportError:
        return False
    from qdrant_client.http.models import PointStruct

    filing_id = filing_dict.get("filing_id", "")
    text = filing_dict.get("raw_text") or filing_dict.get("title", "")

    point_id = _stable_point_id(filing_id, 0)

    point = PointStruct(
        id=point_id,
        vector=embed_text(text),
        payload={
            "filing_id": filing_id,
            "title": filing_dict.get("title", ""),
            "state_code": filing_dict.get("state_code"),
            "sector": filing_dict.get("sector", ""),
            "agency": filing_dict.get("agency", ""),
            "jurisdiction": filing_dict.get("jurisdiction", "state"),
            "source_url": filing_dict.get("source_url", ""),
            "published_date": filing_dict.get("published_date", ""),
            "change_type": filing_dict.get("change_type", "notice"),
            "industry_sectors": filing_dict.get("industry_sectors", []),
        },
    )

    try:
        client.upsert(collection_name=_NS_STATE_FILINGS, points=[point])
        return True
    except Exception as exc:
        logger.warning("Qdrant state filing upsert failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def _qdrant_search(
    client, collection_name: str, query_vector: list[float], query_filter, top_k: int
):
    """Call the appropriate Qdrant search method.

    qdrant-client ≥ 1.12 replaced ``client.search()`` with ``client.query_points()``.
    Try the new API first; fall back to the legacy ``search()`` for older clients.
    """
    if hasattr(client, "query_points"):
        response = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        return response.points
    # Legacy path (qdrant-client < 1.12)
    return client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )


def search_documents(
    client,
    query: str,
    doc_ids: list[str] | None = None,
    collections: list[str] | None = None,
    max_level: int = 1,
    top_k: int = 20,
) -> list[dict]:
    """Search Qdrant collections for relevant content.

    Args:
        client: Qdrant client instance.
        query: Natural-language query to embed and search.
        doc_ids: Optional list of doc_ids to scope search.
        collections: List of collection names to search (default: ns_documents).
        max_level: Maximum L-level to include (0=L0 only, 1=L0+L1, 2=all).
        top_k: Number of results per collection.

    Returns:
        List of result dicts with keys: chunk_id, viking_uri, section_path,
        level, score, doc_id, doc_type, title, abstract, source, payload.
    """
    try:
        import qdrant_client  # noqa: F401  — availability probe
    except ImportError:
        logger.warning("qdrant-client not installed; returning empty search results")
        return []
    # Any import failure *inside* qdrant_client.http.models (a class
    # rename, a broken install) is a structural error and must bubble.
    import qdrant_client.http.models  # noqa: F401

    effective_collections = collections or [_NS_DOCUMENTS]
    query_vector = embed_text(query)
    results: list[dict] = []

    for collection in effective_collections:
        query_filter = _build_filter(doc_ids, max_level)
        try:
            hits = _qdrant_search(client, collection, query_vector, query_filter, top_k)
            for hit in hits:
                payload = hit.payload or {}
                results.append(
                    {
                        "chunk_id": payload.get("chunk_id", ""),
                        "viking_uri": payload.get("viking_uri", ""),
                        "section_path": payload.get("section_path", ""),
                        "level": payload.get("level", 0),
                        "score": hit.score,
                        "doc_id": payload.get("doc_id", ""),
                        "doc_type": payload.get("doc_type", ""),
                        "title": payload.get("title", ""),
                        "abstract": payload.get("abstract", ""),
                        "source": collection,
                        "payload": payload,
                    }
                )
        except Exception as exc:
            logger.warning("Qdrant search in %s failed: %s", collection, exc)

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def _build_filter(doc_ids: list[str] | None, max_level: int) -> Any:
    """Build a Qdrant filter for doc_ids and level constraints.

    Raises:
        ImportError: If qdrant_client is installed but a required class
            has been renamed or removed. This used to be swallowed — the
            ``Must`` class was dropped in qdrant-client ≥ 1.8 and the
            silent ``except ImportError: return None`` shipped every
            Qdrant search run *unfiltered* in production, breaking doc
            isolation. Fail loud instead; the caller
            (``search_documents``) already short-circuits when the
            package itself is absent.
    """
    from qdrant_client.http.models import (
        FieldCondition,
        Filter,
        MatchAny,
        Range,
    )

    conditions = []

    if doc_ids:
        conditions.append(FieldCondition(key="doc_id", match=MatchAny(any=doc_ids)))

    if max_level < 2:
        conditions.append(FieldCondition(key="level", range=Range(lte=max_level)))

    if not conditions:
        return None

    return Filter(must=conditions)
