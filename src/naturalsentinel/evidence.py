"""Evidence ledger domain models."""

from dataclasses import dataclass, field


@dataclass
class EvidenceLedgerEntry:
    evidence_id: str
    source_type: str
    supports: list[str] = field(default_factory=list)
    contradicts: list[str] = field(default_factory=list)
    strength_score: float = 0.0
    novelty_score: float = 0.0
    trace: list[str] = field(default_factory=list)
    source_authority: float = 0.0
    recency_score: float = 0.0
    policy_finality_score: float = 0.0
    jurisdiction_relevance: float = 0.0
    business_line_proximity: float = 0.0
    historical_predictive_usefulness: float = 0.0
    contradiction_risk: float = 0.0
    summary: str = ""
