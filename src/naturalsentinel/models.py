"""Domain types shared across the entire naturalsentinel package."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from naturalsentinel.evidence import EvidenceLedgerEntry


class RegulatoryDomain(Enum):
    SEC = "sec"
    CFPB = "cfpb"
    FED = "fed"
    FDA = "fda"
    EPA = "epa"
    USTR = "ustr"
    # Securities finance & lending domains
    FHFA  = "fhfa"   # Federal Housing Finance Agency
    OCC   = "occ"    # Office of the Comptroller of the Currency
    FINRA = "finra"  # Financial Industry Regulatory Authority
    CFTC  = "cftc"   # Commodity Futures Trading Commission
    FDIC  = "fdic"   # Federal Deposit Insurance Corporation
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


@dataclass
class RegulatoryFiling:
    id: str
    title: str
    domain: RegulatoryDomain
    source_url: str
    published_date: str
    raw_text: str
    change_type: ChangeType = ChangeType.NOTICE
    summary: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ImpactAssessment:
    filing_id: str
    severity: Severity
    affected_business_lines: list[str]
    affected_regulations: list[str]
    compliance_deadline: Optional[str]
    action_items: list[str]
    risk_summary: str
    confidence: float  # 0.0–1.0


@dataclass
class DecisionFrame:
    decision_id: str
    question: str
    scope: str
    time_horizon: str
    affected_entities: list[str] = field(default_factory=list)
    candidate_actions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    evidence_items: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    counterarguments: list[str] = field(default_factory=list)
    confidence: float = 0.0
    expected_revisit_date: Optional[str] = None
    owner: str = "Unassigned"
    audit_refs: list[str] = field(default_factory=list)


@dataclass
class BeliefState:
    """Prior/posterior belief tracking for a specific topic over time.

    Captures how the system's confidence in a particular regulatory topic,
    regime, or obligation has evolved as new filings arrive.  This enables
    the belief-updating engine described in Priority 3 of the Decision
    Framework Iterations.
    """

    topic: str                          # Regime ID, domain:risk_category, or obligation key
    domain: str                         # Regulatory domain namespace (e.g. "sec", "fed")
    prior_confidence: float             # Confidence before the current filing was observed
    posterior_confidence: float         # Confidence after updating on the current filing
    delta_confidence: float             # posterior_confidence − prior_confidence
    delta_drivers: list[str]            # Explanation of what drove the change
    stability_score: float              # 1.0 = very stable; 0.0 = highly volatile
    reversal_risk: float                # 0.0–1.0 probability belief will flip next cycle
    observation_count: int = 0          # Total number of observations recorded for this topic
    last_filing_id: str = ""            # ID of the most recent filing that triggered an update
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class MonitorResult:
    filing: RegulatoryFiling
    impact: ImpactAssessment
    decision: DecisionFrame
    evidence_ledger: list[EvidenceLedgerEntry] = field(default_factory=list)
    belief_states: list[BeliefState] = field(default_factory=list)
    raw_analysis: str = ""
