"""Domain enums: regulatory domains, jurisdictions, states, sectors, severity, change types.

Pure Python enums — no dependencies on framework, storage, or I/O.
Safe to import from anywhere in the codebase.

This was previously part of ``app.naturalsentinel.models``.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field


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


class Jurisdiction(Enum):
    FEDERAL = "federal"
    STATE = "state"


class StateCode(Enum):
    AL = "AL"
    AK = "AK"
    AZ = "AZ"
    AR = "AR"
    CA = "CA"
    CO = "CO"
    CT = "CT"
    DE = "DE"
    FL = "FL"
    GA = "GA"
    HI = "HI"
    ID = "ID"
    IL = "IL"
    IN = "IN"
    IA = "IA"
    KS = "KS"
    KY = "KY"
    LA = "LA"
    ME = "ME"
    MD = "MD"
    MA = "MA"
    MI = "MI"
    MN = "MN"
    MS = "MS"
    MO = "MO"
    MT = "MT"
    NE = "NE"
    NV = "NV"
    NH = "NH"
    NJ = "NJ"
    NM = "NM"
    NY = "NY"
    NC = "NC"
    ND = "ND"
    OH = "OH"
    OK = "OK"
    OR = "OR"
    PA = "PA"
    RI = "RI"
    SC = "SC"
    SD = "SD"
    TN = "TN"
    TX = "TX"
    UT = "UT"
    VT = "VT"
    VA = "VA"
    WA = "WA"
    WV = "WV"
    WI = "WI"
    WY = "WY"
    DC = "DC"


class IndustrySector(Enum):
    FINANCIAL_SERVICES = "financial_services"
    HEALTHCARE = "healthcare"
    INSURANCE = "insurance"
    ENERGY_UTILITIES = "energy_utilities"
    REAL_ESTATE = "real_estate"
    TECHNOLOGY = "technology"
    MANUFACTURING = "manufacturing"
    TRANSPORTATION = "transportation"


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
