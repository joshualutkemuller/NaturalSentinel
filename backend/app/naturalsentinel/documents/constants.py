"""Single source of truth for document intelligence magic values.

Before Phase P1.1 the tier names (``L0``/``L1``/``L2``), OpenViking
filename conventions (``.abstract.md``, ``.overview.md``,
``content.md``), Qdrant collection names (``ns_documents``,
``ns_state_filings``, ``ns_sessions``), token budgets, embedding
dimensions, and the RRF constant were all scattered as hardcoded
strings across 6+ files. A typo or a change in one place silently
diverged from the others — the same anti-pattern that caused the
``analyze_filing_text`` dispatch drift and the ``Must`` import bug.

Importing from this module is now mandatory for anything that used
to inline these values. Architecture rule:

    Magic strings — collection names, OV paths, depth tiers —
    import from ``app.naturalsentinel.documents.constants``. Never
    inline them as string literals.

The ``Tier`` enum is the canonical L0/L1/L2 representation. The
string forms (``"abstract"``, ``"overview"``, ``"detail"``) used on
the HTTP API are mapped via ``DEPTH_TO_TIER`` and
``TIER_TO_DEPTH_STRING``.
"""

from __future__ import annotations

import os
from enum import IntEnum


class Tier(IntEnum):
    """Document detail tiers.

    - ABSTRACT (L0): ~80 tokens, a single-sentence gist
    - OVERVIEW (L1): ~800 tokens, structural summary
    - DETAIL   (L2): ~3000 tokens, full section text
    """

    ABSTRACT = 0
    OVERVIEW = 1
    DETAIL = 2


# ---------------------------------------------------------------------------
# Tier <-> public API string mapping
# ---------------------------------------------------------------------------

DEPTH_TO_TIER: dict[str, Tier] = {
    "abstract": Tier.ABSTRACT,
    "overview": Tier.OVERVIEW,
    "detail": Tier.DETAIL,
}

TIER_TO_DEPTH_STRING: dict[Tier, str] = {v: k for k, v in DEPTH_TO_TIER.items()}


# ---------------------------------------------------------------------------
# Token budgets
# ---------------------------------------------------------------------------

# Rough token averages per tier, used by _assemble_tiered to stay within
# the caller's token_budget without overshooting.
TIER_AVG_TOKENS: dict[Tier, int] = {
    Tier.ABSTRACT: 80,
    Tier.OVERVIEW: 800,
    Tier.DETAIL: 3000,
}

DEFAULT_TOKEN_BUDGET: int = int(os.environ.get("SENTINEL_TOKEN_BUDGET", "6144"))
WORDS_PER_TOKEN: float = 0.75  # 1 token ≈ 0.75 words


# ---------------------------------------------------------------------------
# OpenViking file conventions
# ---------------------------------------------------------------------------

OV_DOCUMENT_ROOT: str = "viking://documents"
OV_SESSIONS_ROOT: str = "viking://sessions"

OV_META_FILE: str = "meta.json"

# Filenames written per node at each tier (see documents/openviking_service.py)
OV_FILENAMES: dict[Tier, str] = {
    Tier.ABSTRACT: ".abstract.md",
    Tier.OVERVIEW: ".overview.md",
    Tier.DETAIL: "content.md",
}


# ---------------------------------------------------------------------------
# Qdrant collections
# ---------------------------------------------------------------------------

QDRANT_NS_DOCUMENTS: str = "ns_documents"
QDRANT_NS_STATE_FILINGS: str = "ns_state_filings"
QDRANT_NS_SESSIONS: str = "ns_sessions"

# Dimension of the embedding vectors written to every collection.
# OpenAI text-embedding-3-large = 3072; override via env for other providers.
QDRANT_EMBEDDING_DIM: int = int(os.environ.get("SENTINEL_EMBEDDING_DIM", "3072"))

QDRANT_BATCH_SIZE: int = 100


# ---------------------------------------------------------------------------
# Retrieval — Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

# Standard RRF constant. Higher k yields smoother blending across rankers.
RRF_K: int = 60


__all__ = [
    "DEFAULT_TOKEN_BUDGET",
    "DEPTH_TO_TIER",
    "OV_DOCUMENT_ROOT",
    "OV_FILENAMES",
    "OV_META_FILE",
    "OV_SESSIONS_ROOT",
    "QDRANT_BATCH_SIZE",
    "QDRANT_EMBEDDING_DIM",
    "QDRANT_NS_DOCUMENTS",
    "QDRANT_NS_SESSIONS",
    "QDRANT_NS_STATE_FILINGS",
    "RRF_K",
    "TIER_AVG_TOKENS",
    "TIER_TO_DEPTH_STRING",
    "Tier",
    "WORDS_PER_TOKEN",
]
