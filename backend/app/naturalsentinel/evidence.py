"""Evidence ledger domain models."""

from pydantic import BaseModel, Field


class EvidenceLedgerEntry(BaseModel):
    """Single piece of evidence with multi-dimensional scoring.

    Citation location fields (source_url, viking_uri, line_start, line_end,
    page_number, excerpt, section_path) are populated for all document-grounded
    evidence resolved via the [CITE:chunk_id] extraction pipeline.
    """

    evidence_id: str
    source_type: str

    # Citation location — populated when evidence is resolved from a DocumentChunk
    source_url: str = ""  # direct URL to the original source document
    viking_uri: str = ""  # viking:// URI pointing to the exact passage
    line_start: int | None = None  # 1-indexed line number in original source
    line_end: int | None = None
    page_number: int | None = None  # PDF page; None for HTML/text sources
    excerpt: str = ""  # verbatim passage (≤200 chars) for inline display
    section_path: str = ""  # human-readable section label ("§3 ¶2")

    # Claim linkage
    supports: list[str] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)

    # Multi-dimensional scoring
    strength_score: float = Field(default=0.0, ge=0.0, le=1.0)
    novelty_score: float = Field(default=0.0, ge=0.0, le=1.0)
    trace: list[str] = Field(default_factory=list)
    source_authority: float = Field(default=0.0, ge=0.0, le=1.0)
    recency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    policy_finality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    jurisdiction_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    business_line_proximity: float = Field(default=0.0, ge=0.0, le=1.0)
    historical_predictive_usefulness: float = Field(default=0.0, ge=0.0, le=1.0)
    contradiction_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
