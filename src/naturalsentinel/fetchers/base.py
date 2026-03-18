"""Filing fetcher and domain-to-business-line mappings."""

from datetime import datetime, timedelta

from naturalsentinel.models import ChangeType, RegulatoryDomain, RegulatoryFiling
from naturalsentinel.fetchers.sample_data import SAMPLE_FILINGS

# Maps domain -> list of portfolio / business lines typically affected
DOMAIN_BUSINESS_LINES: dict[str, list[str]] = {
    "sec": [
        "Public Equities", "Investment Banking", "Corporate Finance",
        "ESG / Sustainability", "Investor Relations", "Audit & Assurance",
    ],
    "cfpb": [
        "Consumer Lending", "Credit Cards", "Mortgage Banking",
        "Auto Finance", "Fintech Partnerships", "Collections",
    ],
    "fed": [
        "Commercial Banking", "Digital Assets / Crypto", "Treasury & ALM",
        "Risk Management", "Capital Markets", "Payments",
    ],
    "fda": [
        "Medical Devices", "Pharmaceuticals", "Biotech",
        "Digital Health / SaMD", "Clinical Trials", "Regulatory Affairs",
    ],
    "epa": [
        "Manufacturing", "Energy & Utilities", "Transportation",
        "Real Estate & Construction", "Agriculture", "Insurance (Environmental)",
    ],
    "ustr": [
        "Supply Chain / Procurement", "Semiconductor Manufacturing",
        "Defense Contracting", "Consumer Electronics", "Critical Minerals",
        "International Trade Finance",
    ],
    # Securities finance & lending domains
    "fhfa": [
        "Agency Lending", "Mortgage Banking", "Agency MBS / TBA",
        "GSE Collateral Management", "Conforming Loan Origination",
        "Credit Risk Transfer (CRT)", "Prepayment Modelling",
    ],
    "occ": [
        "Secured Lending", "Prime Lending", "Leveraged Finance",
        "Commercial Real Estate Lending", "Capital Planning",
        "Model Risk Management", "Credit Portfolio Management",
    ],
    "finra": [
        "Prime Brokerage", "Securities Lending", "Margin Lending",
        "Repo / Reverse Repo", "TBA / MBS Trading", "Broker-Dealer Operations",
        "Customer Margin Accounts",
    ],
    "cftc": [
        "Derivatives / Swaps", "Initial Margin (IM/SIMM)",
        "Counterparty Credit Risk", "Cleared vs Uncleared Swaps",
        "Commodity Finance", "FX Prime Brokerage", "CVA / MVA Hedging",
    ],
    "fdic": [
        "Commercial Banking", "Deposit Funding", "Capital Adequacy",
        "Resolution Planning", "Secured Lending", "Brokered Deposits",
        "Stress Testing",
    ],
    "basel": [
        "Capital Optimization", "RWA Modelling", "SA-CCR",
        "Leverage Ratio / SLR", "NSFR / LCR", "Output Floor",
        "Internal Models (FRTB / IRBA)", "XVA Desk",
    ],
}


def fetch_filings(
    domains: list[RegulatoryDomain] | None = None,
    since_days: int = 30,
) -> list[RegulatoryFiling]:
    """
    Fetch regulatory filings.

    In production this would hit real APIs:
      - SEC EDGAR Full-Text Search API
      - Federal Register API (federalregister.gov/api/v1)
      - CFPB regulatory publications
      - FDA guidance document feeds
      - EPA Federal Register notices
      - USTR Federal Register & press releases

    For this release we return curated sample data.
    """
    cutoff = datetime.utcnow() - timedelta(days=since_days)
    results = []
    for raw in SAMPLE_FILINGS:
        pub = datetime.fromisoformat(raw["published_date"])
        domain = RegulatoryDomain(raw["domain"])
        if domains and domain not in domains:
            continue
        if pub >= cutoff:
            results.append(
                RegulatoryFiling(
                    id=raw["id"],
                    title=raw["title"],
                    domain=domain,
                    source_url=raw["source_url"],
                    published_date=raw["published_date"],
                    change_type=ChangeType(raw["change_type"]),
                    raw_text=raw["raw_text"],
                )
            )
    return results
