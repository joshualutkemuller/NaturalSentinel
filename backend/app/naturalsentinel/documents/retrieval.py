"""Tiered context retrieval (Layer 4).

Implements the dual-path retrieval strategy described in the PRD:
  Path A: Qdrant kNN search
  Path B: OpenViking hierarchical search
  Merge:  Reciprocal Rank Fusion
  Assembly: L0 scan → promote top candidates to L1 → L2 on demand

Public entry point::

    from app.naturalsentinel.documents.retrieval import recall_context

    result = recall_context(
        query="What are the indemnification obligations?",
        ov_client=...,
        qdrant_client=...,
        doc_ids=["uuid-..."],
        token_budget=6144,
        depth="overview",
    )
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TOKEN_BUDGET = 6144
_WORDS_PER_TOKEN = 0.75  # rough approximation: 1 token ≈ 0.75 words
_L0_AVG_TOKENS = 80
_L1_AVG_TOKENS = 800
_L2_AVG_TOKENS = 3000


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def recall_context(
    query: str,
    ov_client=None,
    qdrant_client=None,
    doc_ids: list[str] | None = None,
    collections: list[str] | None = None,
    token_budget: int = _DEFAULT_TOKEN_BUDGET,
    depth: str = "overview",
    include_cross_references: bool = True,
) -> dict[str, Any]:
    """Retrieve relevant document context for a query.

    Args:
        query: Natural-language question or information need.
        ov_client: OpenViking SyncHTTPClient. Pass None to skip OV retrieval.
        qdrant_client: Qdrant client. Pass None to skip vector search.
        doc_ids: Scope search to these documents. None = all indexed docs.
        collections: Qdrant collections to search. Default: ns_documents.
        token_budget: Maximum tokens in the assembled context.
        depth: Maximum level to include — ``"abstract"`` (L0), ``"overview"``
            (L1), or ``"detail"`` (L2).
        include_cross_references: Whether to follow and include cross-referenced
            sections (OpenViking only).

    Returns:
        Dict with keys: context_blocks, total_tokens, retrieval_trajectory.
    """
    max_level = {"abstract": 0, "overview": 1, "detail": 2}.get(depth, 1)

    # ── Path A: Qdrant kNN search ──────────────────────────────────────────
    qdrant_results: list[dict] = []
    if qdrant_client is not None:
        try:
            from app.naturalsentinel.documents.qdrant_service import search_documents

            qdrant_results = search_documents(
                client=qdrant_client,
                query=query,
                doc_ids=doc_ids,
                collections=collections,
                max_level=min(max_level, 1),  # search L0/L1 first for speed
                top_k=20,
            )
        except Exception as exc:
            logger.warning("Qdrant retrieval failed: %s", exc)

    # ── Path B: OpenViking hierarchical search ─────────────────────────────
    ov_results: list[dict] = []
    if ov_client is not None:
        try:
            target_uri = "viking://documents/"
            if doc_ids and len(doc_ids) == 1:
                target_uri = f"viking://documents/{doc_ids[0]}"
            raw_ov = ov_client.find(query=query, target_uri=target_uri, limit=15)
            ov_results = _normalize_ov_results(raw_ov)
        except Exception as exc:
            logger.debug("OpenViking search failed: %s", exc)

    # ── Merge via Reciprocal Rank Fusion ───────────────────────────────────
    merged = _reciprocal_rank_fusion(qdrant_results, ov_results)
    rrf_count = len(merged)

    # ── Tiered assembly within token budget ───────────────────────────────
    context_blocks, total_tokens, dirs_traversed = _assemble_tiered(
        merged, ov_client, qdrant_client, token_budget, max_level
    )

    # ── Cross-references (optional) ────────────────────────────────────────
    if include_cross_references and ov_client is not None and context_blocks:
        _expand_cross_references(context_blocks, ov_client, token_budget - total_tokens)

    return {
        "context_blocks": context_blocks,
        "total_tokens": total_tokens,
        "retrieval_trajectory": {
            "qdrant_candidates": len(qdrant_results),
            "ov_candidates": len(ov_results),
            "merged_unique": rrf_count,
            "returned": len(context_blocks),
            "directories_traversed": dirs_traversed,
        },
    }


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

_RRF_K = 60  # standard constant; higher = smoother blending


def _reciprocal_rank_fusion(
    qdrant_results: list[dict],
    ov_results: list[dict],
) -> list[dict]:
    """Merge two ranked lists using Reciprocal Rank Fusion.

    Returns a deduplicated list sorted by fused score descending.
    Items from both lists are unified by ``viking_uri``.
    """
    # Track fused scores and payloads by URI
    scores: dict[str, float] = {}
    payloads: dict[str, dict] = {}

    def _key(r: dict) -> str:
        uri = r.get("viking_uri", "")
        # Normalise to base URI (strip level suffix if any)
        return uri.split("?")[0]

    for rank, r in enumerate(qdrant_results, 1):
        k = _key(r)
        scores[k] = scores.get(k, 0.0) + 1.0 / (_RRF_K + rank)
        if k not in payloads:
            payloads[k] = r

    for rank, r in enumerate(ov_results, 1):
        k = _key(r)
        scores[k] = scores.get(k, 0.0) + 1.0 / (_RRF_K + rank)
        if k not in payloads:
            payloads[k] = r

    merged: list[dict] = []
    for uri, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        item = dict(payloads[uri])
        item["rrf_score"] = round(score, 6)
        merged.append(item)

    return merged


# ---------------------------------------------------------------------------
# Tiered assembly
# ---------------------------------------------------------------------------


def _assemble_tiered(
    candidates: list[dict],
    ov_client,
    qdrant_client,
    token_budget: int,
    max_level: int,
) -> tuple[list[dict], int, list[str]]:
    """Assemble context blocks within the token budget.

    Strategy:
    1. Load L0 abstracts for all candidates (cheapest)
    2. Promote top candidates to L1 with remaining budget
    3. Mark L2 as available hints without loading inline

    Returns (context_blocks, total_tokens_used, directories_traversed).
    """
    blocks: list[dict] = []
    total_tokens = 0
    dirs_traversed: list[str] = []

    # Phase 1: Load L0 for all
    for c in candidates:
        abstract = _load_content(c, 0, ov_client)
        tokens = _estimate_tokens(abstract)
        if total_tokens + tokens > token_budget:
            break
        block = {
            "uri": c.get("viking_uri", ""),
            "doc_id": c.get("doc_id", ""),
            "section_path": c.get("section_path", ""),
            "level": "abstract",
            "content": abstract,
            "relevance_score": c.get("rrf_score", c.get("score", 0.0)),
            "source": c.get("source", "merged"),
            "l1_available": max_level >= 1,
            "l2_available": max_level >= 2,
        }
        blocks.append(block)
        total_tokens += tokens
        uri_dir = "/".join(c.get("viking_uri", "").split("/")[:-1])
        if uri_dir and uri_dir not in dirs_traversed:
            dirs_traversed.append(uri_dir)

    if max_level < 1:
        return blocks, total_tokens, dirs_traversed

    # Phase 2: Promote top candidates to L1
    budget_remaining = token_budget - total_tokens
    for i, block in enumerate(blocks):
        if budget_remaining < _L1_AVG_TOKENS:
            break
        candidate = candidates[i]
        overview = _load_content(candidate, 1, ov_client)
        tokens = _estimate_tokens(overview)
        if total_tokens + tokens > token_budget:
            continue
        block["level"] = "overview"
        block["content"] = overview
        # Keep the L0 accessible as a separate key
        block["abstract"] = block.get("content", "")[:200]
        delta = tokens - _L0_AVG_TOKENS  # replace L0 cost with L1 cost
        total_tokens = max(0, total_tokens + delta)
        budget_remaining -= tokens

    return blocks, total_tokens, dirs_traversed


def _load_content(candidate: dict, level: int, ov_client) -> str:
    """Fetch content for a candidate at the requested level.

    Falls back to payload fields if OpenViking is unavailable.
    """
    uri = candidate.get("viking_uri", "")
    payload = candidate.get("payload", candidate)

    if ov_client is not None and uri:
        try:
            if level == 0:
                return ov_client.abstract(uri) or payload.get("abstract", "")
            elif level == 1:
                return ov_client.overview(uri) or payload.get("abstract", "")
            else:
                return ov_client.read(uri) or payload.get("excerpt", "")
        except Exception:
            pass

    # Fallback to payload
    if level == 0:
        return payload.get("abstract", "")
    elif level == 1:
        return payload.get("abstract", "") + "\n\n" + payload.get("excerpt", "")[:500]
    return payload.get("excerpt", "")


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: words / 0.75."""
    return int(len(text.split()) / _WORDS_PER_TOKEN)


# ---------------------------------------------------------------------------
# Cross-reference expansion
# ---------------------------------------------------------------------------


def _expand_cross_references(
    blocks: list[dict], ov_client, budget_remaining: int
) -> None:
    """Append L0 abstracts for cross-referenced sections where budget allows."""
    seen_uris = {b["uri"] for b in blocks}
    xref_blocks: list[dict] = []
    tokens_used = 0

    for block in list(blocks):
        uri = block.get("uri", "")
        if not uri:
            continue
        try:
            rels = ov_client.relations(uri)
        except Exception:
            continue
        for rel in (rels or [])[:5]:
            target_uri = rel.get("target", "")
            if not target_uri or target_uri in seen_uris:
                continue
            try:
                abstract = ov_client.abstract(target_uri) or ""
            except Exception:
                abstract = ""
            tokens = _estimate_tokens(abstract)
            if tokens_used + tokens > budget_remaining:
                break
            xref_blocks.append(
                {
                    "uri": target_uri,
                    "doc_id": block.get("doc_id", ""),
                    "section_path": rel.get("label", target_uri),
                    "level": "abstract",
                    "content": abstract,
                    "relevance_score": 0.0,
                    "source": "cross_reference",
                }
            )
            seen_uris.add(target_uri)
            tokens_used += tokens

    blocks.extend(xref_blocks)


# ---------------------------------------------------------------------------
# OpenViking result normalizer
# ---------------------------------------------------------------------------


def _normalize_ov_results(raw_ov: Any) -> list[dict]:
    """Convert OpenViking find() results to the standard result dict shape."""
    if not raw_ov:
        return []
    results: list[dict] = []

    items = raw_ov if isinstance(raw_ov, list) else raw_ov.get("results", [])
    for item in items:
        if isinstance(item, dict):
            uri = item.get("uri") or item.get("path", "")
            score = float(item.get("score", 0.0))
            results.append(
                {
                    "viking_uri": uri,
                    "section_path": uri,
                    "score": score,
                    "doc_id": _doc_id_from_uri(uri),
                    "source": "openviking",
                    "payload": item,
                }
            )
    return results


def _doc_id_from_uri(uri: str) -> str:
    """Extract doc_id from a viking://documents/{doc_id}/... URI."""
    parts = uri.replace("viking://", "").split("/")
    if len(parts) >= 2 and parts[0] == "documents":
        return parts[1]
    return ""
