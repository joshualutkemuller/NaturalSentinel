"""Evidence ledger domain models."""

from pydantic import BaseModel, Field


class EvidenceLedgerEntry(BaseModel):
    """Single piece of evidence with multi-dimensional scoring."""

    evidence_id: str
    source_type: str
    supports: list[str] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)
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
