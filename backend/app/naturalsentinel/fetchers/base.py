"""Filing fetcher and domain-to-business-line mappings."""

import logging
from datetime import datetime, timedelta

from app.naturalsentinel.fetchers.sample_data import SAMPLE_FILINGS
from app.naturalsentinel.models import ChangeType, RegulatoryDomain, RegulatoryFiling

logger = logging.getLogger(__name__)

# Maps domain -> list of portfolio / business lines typically affected
DOMAIN_BUSINESS_LINES: dict[str, list[str]] = {
    "sec": [
        "Public Equities",
        "Investment Banking",
        "Corporate Finance",
        "ESG / Sustainability",
        "Investor Relations",
        "Audit & Assurance",
    ],
    "cfpb": [
        "Consumer Lending",
        "Credit Cards",
        "Mortgage Banking",
        "Auto Finance",
        "Fintech Partnerships",
        "Collections",
    ],
    "fed": [
        "Commercial Banking",
        "Digital Assets / Crypto",
        "Treasury & ALM",
        "Risk Management",
        "Capital Markets",
        "Payments",
    ],
    "fda": [
        "Medical Devices",
        "Pharmaceuticals",
        "Biotech",
        "Digital Health / SaMD",
        "Clinical Trials",
        "Regulatory Affairs",
    ],
    "epa": [
        "Manufacturing",
        "Energy & Utilities",
        "Transportation",
        "Real Estate & Construction",
        "Agriculture",
        "Insurance (Environmental)",
    ],
    "ustr": [
        "Supply Chain / Procurement",
        "Semiconductor Manufacturing",
        "Defense Contracting",
        "Consumer Electronics",
        "Critical Minerals",
        "International Trade Finance",
    ],
    # Securities finance & lending domains
    "fhfa": [
        "Agency Lending",
        "Mortgage Banking",
        "Agency MBS / TBA",
        "GSE Collateral Management",
        "Conforming Loan Origination",
        "Credit Risk Transfer (CRT)",
        "Prepayment Modelling",
    ],
    "occ": [
        "Secured Lending",
        "Prime Lending",
        "Leveraged Finance",
        "Commercial Real Estate Lending",
        "Capital Planning",
        "Model Risk Management",
        "Credit Portfolio Management",
    ],
    "finra": [
        "Prime Brokerage",
        "Securities Lending",
        "Margin Lending",
        "Repo / Reverse Repo",
        "TBA / MBS Trading",
        "Broker-Dealer Operations",
        "Customer Margin Accounts",
    ],
    "cftc": [
        "Derivatives / Swaps",
        "Initial Margin (IM/SIMM)",
        "Counterparty Credit Risk",
        "Cleared vs Uncleared Swaps",
        "Commodity Finance",
        "FX Prime Brokerage",
        "CVA / MVA Hedging",
    ],
    "fdic": [
        "Commercial Banking",
        "Deposit Funding",
        "Capital Adequacy",
        "Resolution Planning",
        "Secured Lending",
        "Brokered Deposits",
        "Stress Testing",
    ],
    "basel": [
        "Capital Optimization",
        "RWA Modelling",
        "SA-CCR",
        "Leverage Ratio / SLR",
        "NSFR / LCR",
        "Output Floor",
        "Internal Models (FRTB / IRBA)",
        "XVA Desk",
    ],
}


def fetch_filings(
    domains: list[RegulatoryDomain] | None = None,
    since_days: int = 30,
    live: bool = False,
    fetch_full_text: bool = True,
    http_client=None,
) -> list[RegulatoryFiling]:
    """Fetch regulatory filings.

    Args:
        domains: Optional domain filter.  ``None`` = all supported domains.
        since_days: Look-back window in days (default 30).
        live: If ``True``, fetch from live public sources (Federal Register
            API, EDGAR, BIS, FINRA) instead of returning the curated sample
            dataset.  Requires network access; gracefully falls back to
            sample data if all live sources fail.
        fetch_full_text: When ``live=True``, whether to retrieve the full
            HTML document text for each filing (default ``True``).  Set
            ``False`` to use abstract/summary only for faster ingestion.
        http_client: Optional :class:`~naturalsentinel.fetchers.live.http_client.HTTPClient`
            to inject for testing.  When ``None``, each sub-fetcher creates
            its own rate-limited client.

    Returns:
        List of :class:`~naturalsentinel.models.RegulatoryFiling` objects.

    Live sources
    ------------
    Federal Register API   FED, CFPB, OCC, FDIC, CFTC, SEC, EPA, USTR, FHFA, FDA
    SEC EDGAR EFTS         SEC (supplementary)
    BIS/BCBS               BASEL
    FINRA notices          FINRA
    """
    if live:
        return _fetch_live(domains, since_days, fetch_full_text, http_client)
    return _fetch_sample(domains, since_days)


def _fetch_sample(
    domains: list[RegulatoryDomain] | None,
    since_days: int,
) -> list[RegulatoryFiling]:
    """Return filings from the curated sample dataset."""
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


def _fetch_live(
    domains: list[RegulatoryDomain] | None,
    since_days: int,
    fetch_full_text: bool,
    http_client,
) -> list[RegulatoryFiling]:
    """Coordinate live ingestion across all public sources."""
    # Import live fetchers here to keep the lazy import pattern
    from app.naturalsentinel.fetchers.live import bis, edgar, federal_register, finra

    domain_strs: list[str] = (
        [d.value for d in domains] if domains else list(DOMAIN_BUSINESS_LINES.keys())
    )

    raw_filings: list[dict] = []

    # --- Federal Register (primary source for most US agencies) ---
    fr_domains = [d for d in domain_strs if d in federal_register.DOMAIN_TO_AGENCY]
    if fr_domains:
        try:
            fr_results = federal_register.fetch(
                domains=fr_domains,
                since_days=since_days,
                fetch_full_text=fetch_full_text,
                client=http_client,
            )
            raw_filings.extend(fr_results)
            logger.info("Federal Register: fetched %d filings", len(fr_results))
        except Exception as exc:
            logger.warning("Federal Register fetch failed: %s", exc)

    # --- SEC EDGAR (supplementary SEC-specific content) ---
    if not domains or RegulatoryDomain.SEC in domains:
        try:
            edgar_results = edgar.fetch(
                since_days=since_days,
                fetch_full_text=fetch_full_text,
                client=http_client,
            )
            raw_filings.extend(edgar_results)
            logger.info("EDGAR: fetched %d filings", len(edgar_results))
        except Exception as exc:
            logger.warning("EDGAR fetch failed: %s", exc)

    # --- BIS/BCBS (Basel domain) ---
    if not domains or RegulatoryDomain.BASEL in domains:
        try:
            bis_results = bis.fetch(
                since_days=max(since_days, 90),  # BIS publishes less frequently
                fetch_full_text=fetch_full_text,
                client=http_client,
            )
            raw_filings.extend(bis_results)
            logger.info("BIS/BCBS: fetched %d filings", len(bis_results))
        except Exception as exc:
            logger.warning("BIS fetch failed: %s", exc)

    # --- FINRA notices ---
    if not domains or RegulatoryDomain.FINRA in domains:
        try:
            finra_results = finra.fetch(
                since_days=max(since_days, 60),
                fetch_full_text=fetch_full_text,
                client=http_client,
            )
            raw_filings.extend(finra_results)
            logger.info("FINRA: fetched %d filings", len(finra_results))
        except Exception as exc:
            logger.warning("FINRA fetch failed: %s", exc)

    if not raw_filings:
        logger.warning(
            "All live sources returned zero filings — falling back to sample data"
        )
        return _fetch_sample(domains, since_days)

    # De-duplicate by ID
    seen: set[str] = set()
    filings: list[RegulatoryFiling] = []
    for raw in raw_filings:
        fid = raw.get("id", "")
        if not fid or fid in seen:
            continue
        seen.add(fid)
        try:
            filings.append(_raw_to_filing(raw))
        except Exception as exc:
            logger.debug("Skipping malformed filing %s: %s", fid, exc)

    return filings


def _raw_to_filing(raw: dict) -> RegulatoryFiling:
    """Convert a raw ingestion dict to a :class:`RegulatoryFiling`."""
    domain_str = raw.get("domain", "sec")
    try:
        domain = RegulatoryDomain(domain_str)
    except ValueError:
        domain = RegulatoryDomain.SEC

    change_type_str = raw.get("change_type", "notice")
    try:
        change_type = ChangeType(change_type_str)
    except ValueError:
        change_type = ChangeType.NOTICE

    pub_date = raw.get("published_date", "")
    if not pub_date:
        pub_date = datetime.utcnow().strftime("%Y-%m-%d")

    return RegulatoryFiling(
        id=raw["id"],
        title=raw.get("title", raw["id"]),
        domain=domain,
        source_url=raw.get("source_url", ""),
        published_date=pub_date,
        change_type=change_type,
        raw_text=raw.get("raw_text", ""),
    )
