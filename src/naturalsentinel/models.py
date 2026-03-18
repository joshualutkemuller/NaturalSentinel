"""Domain types shared across the entire naturalsentinel package."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


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
class MonitorResult:
    filing: RegulatoryFiling
    impact: ImpactAssessment
    raw_analysis: str
