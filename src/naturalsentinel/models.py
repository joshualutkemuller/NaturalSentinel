"""Domain types shared across the entire naturalsentinel package."""

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from naturalsentinel.evidence import EvidenceLedgerEntry

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RegulatoryDomain(Enum):
    SEC = "sec"
    CFPB = "cfpb"
    FED = "fed"
    FDA = "fda"
    EPA = "epa"
    USTR = "ustr"
    # Securities finance & lending domains
    FHFA = "fhfa"  # Federal Housing Finance Agency
    OCC = "occ"  # Office of the Comptroller of the Currency
    FINRA = "finra"  # Financial Industry Regulatory Authority
    CFTC = "cftc"  # Commodity Futures Trading Commission
    FDIC = "fdic"  # Federal Deposit Insurance Corporation
    BASEL = "basel"  # Basel Committee on Banking Supervision


class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeType(Enum):
    PROPOSED_RULE = "proposed_rule"
    FINAL_RULE = "final_rule"
    GUIDANCE = "guidance"
    ENFORCEMENT = "enforcement"
    NOTICE = "notice"
    AMENDMENT = "amendment"
    EXECUTIVE_ORDER = "executive_order"


# ---------------------------------------------------------------------------
# Reusable annotated types
# ---------------------------------------------------------------------------

UnitFloat = Annotated[float, Field(ge=0.0, le=1.0)]
"""A float constrained to [0.0, 1.0]."""

# ---------------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------------


class RegulatoryFiling(BaseModel):
    """A single regulatory document ingested from a government source."""

    model_config = ConfigDict(use_enum_values=False)

    id: str
    title: str
    domain: RegulatoryDomain
    source_url: str
    published_date: str
    raw_text: str
    change_type: ChangeType = ChangeType.NOTICE
    summary: str = ""
    fetched_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ImpactAssessment(BaseModel):
    """LLM-extracted structured analysis of a regulatory filing's impact."""

    model_config = ConfigDict(use_enum_values=False)

    filing_id: str
    severity: Severity
    affected_business_lines: list[str]
    affected_regulations: list[str]
    compliance_deadline: str | None
    action_items: list[str]
    risk_summary: str
    confidence: UnitFloat
    # Lineage / explainability fields (optional — populated by AnalyzeFilingSkill)
    citations: dict = Field(default_factory=dict)
    trace_id: str | None = None
    provenance: dict = Field(default_factory=dict)


class DecisionFrame(BaseModel):
    """Structured decision context for a regulatory question."""

    decision_id: str
    question: str
    scope: str
    time_horizon: str
    affected_entities: list[str] = Field(default_factory=list)
    candidate_actions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    evidence_items: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    counterarguments: list[str] = Field(default_factory=list)
    confidence: UnitFloat = 0.0
    expected_revisit_date: str | None = None
    owner: str = "Unassigned"
    audit_refs: list[str] = Field(default_factory=list)


class BeliefState(BaseModel):
    """Prior/posterior belief tracking for a specific topic over time.

    Captures how the system's confidence in a particular regulatory topic,
    regime, or obligation has evolved as new filings arrive.  This enables
    the belief-updating engine described in Priority 3 of the Decision
    Framework Iterations.
    """

    topic: str
    domain: str
    prior_confidence: UnitFloat
    posterior_confidence: UnitFloat
    delta_confidence: float = Field(ge=-1.0, le=1.0)
    delta_drivers: list[str]
    stability_score: UnitFloat
    reversal_risk: UnitFloat
    observation_count: int = Field(default=0, ge=0)
    last_filing_id: str = ""
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    @model_validator(mode="after")
    def _check_delta_matches(self) -> "BeliefState":
        expected = round(self.posterior_confidence - self.prior_confidence, 10)
        if abs(self.delta_confidence - expected) > 1e-6:
            raise ValueError(
                f"delta_confidence ({self.delta_confidence}) must equal "
                f"posterior - prior ({expected})"
            )
        return self


class MonitorResult(BaseModel):
    """Aggregated output from a complete filing analysis cycle."""

    filing: RegulatoryFiling
    impact: ImpactAssessment
    decision: DecisionFrame
    evidence_ledger: list[EvidenceLedgerEntry] = Field(default_factory=list)
    belief_states: list[BeliefState] = Field(default_factory=list)
    raw_analysis: str = ""
