"""Filing fetcher and domain-to-business-line mappings."""

import logging
from datetime import datetime, timedelta

from app.naturalsentinel.fetchers.sample_data import SAMPLE_FILINGS
from app.naturalsentinel.models import (
    ChangeType,
    IndustrySector,
    Jurisdiction,
    RegulatoryDomain,
    RegulatoryFiling,
    StateCode,
)

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
    sectors: list[IndustrySector] | None = None,
    state_codes: list[StateCode] | None = None,
    jurisdiction: Jurisdiction | None = None,
    since_days: int = 30,
    live: bool = False,
    fetch_full_text: bool = True,
    http_client=None,
) -> list[RegulatoryFiling]:
    """Fetch regulatory filings.

    Args:
        domains: Optional federal domain filter.  ``None`` = all supported domains.
        sectors: Optional industry sector filter.  When provided, federal domains
            are auto-expanded via ``SECTOR_TO_FEDERAL_DOMAINS`` and state fetchers
            are filtered to matching sectors.
        state_codes: Optional state filter for state-level filings.  ``None`` = all
            registered states.
        jurisdiction: Optional filter — ``FEDERAL`` returns only federal filings,
            ``STATE`` returns only state filings, ``None`` returns both (when live).
        since_days: Look-back window in days (default 30).
        live: If ``True``, fetch from live public sources instead of the curated
            sample dataset.  Requires network access; gracefully falls back to
            sample data if all live sources fail.
        fetch_full_text: When ``live=True``, whether to retrieve the full HTML
            document text for each filing (default ``True``).  Set ``False`` to
            use abstract/summary only for faster ingestion.
        http_client: Optional HTTPClient to inject for testing.

    Returns:
        List of :class:`~naturalsentinel.models.RegulatoryFiling` objects.

    Live sources
    ------------
    Federal: Federal Register API, SEC EDGAR, BIS/BCBS, FINRA
    State:   Open States API, state agency RSS feeds, NASAA, NAIC, CSBS
    """
    if not live:
        return _fetch_sample(domains, since_days)

    # Auto-expand domains from sectors
    effective_domains = _expand_domains(domains, sectors)
    state_code_strs = [s.value for s in state_codes] if state_codes else None
    sector_strs = [s.value for s in sectors] if sectors else None

    filings: list[RegulatoryFiling] = []

    if jurisdiction != Jurisdiction.STATE:
        # Fetch federal filings
        federal = _fetch_live(
            effective_domains, since_days, fetch_full_text, http_client
        )
        filings.extend(federal)

    if jurisdiction != Jurisdiction.FEDERAL:
        # Fetch state filings
        state = _fetch_state_live(sector_strs, state_code_strs, since_days)
        filings.extend(state)

    if not filings:
        logger.warning(
            "All live sources returned zero filings — falling back to sample data"
        )
        return _fetch_sample(domains, since_days)

    return filings


def _expand_domains(
    domains: list[RegulatoryDomain] | None,
    sectors: list[IndustrySector] | None,
) -> list[RegulatoryDomain] | None:
    """Merge explicit domains with sector-derived domains."""
    if not sectors:
        return domains

    from app.naturalsentinel.fetchers.state_domains import SECTOR_TO_FEDERAL_DOMAINS

    expanded: set[str] = set()
    if domains:
        expanded.update(d.value for d in domains)
    for sector in sectors:
        expanded.update(SECTOR_TO_FEDERAL_DOMAINS.get(sector.value, []))

    if not expanded:
        return domains

    result: list[RegulatoryDomain] = []
    for val in expanded:
        try:
            result.append(RegulatoryDomain(val))
        except ValueError:
            pass
    return result or None


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


def _fetch_state_live(
    sectors: list[str] | None,
    state_codes: list[str] | None,
    since_days: int,
) -> list[RegulatoryFiling]:
    """Coordinate live ingestion from all state-level regulatory sources."""
    from app.naturalsentinel.fetchers.live import (
        csbs,
        naic,
        nasaa,
        open_states,
        state_rss,
    )

    raw_filings: list[dict] = []

    # --- Open States API (legislative bills) ---
    try:
        os_results = open_states.fetch(
            state_codes=state_codes,
            sectors=sectors,
            since_days=since_days,
        )
        raw_filings.extend(os_results)
        logger.info("Open States: fetched %d bills", len(os_results))
    except Exception as exc:
        logger.warning("Open States fetch failed: %s", exc)

    # --- State agency RSS feeds ---
    try:
        rss_results = state_rss.fetch(
            state_codes=state_codes,
            sectors=sectors,
            since_days=since_days,
        )
        raw_filings.extend(rss_results)
        logger.info("State RSS: fetched %d entries", len(rss_results))
    except Exception as exc:
        logger.warning("State RSS fetch failed: %s", exc)

    # --- NASAA (securities — financial_services) ---
    if not sectors or "financial_services" in sectors:
        try:
            nasaa_results = nasaa.fetch(since_days=since_days, state_codes=state_codes)
            raw_filings.extend(nasaa_results)
            logger.info("NASAA: fetched %d entries", len(nasaa_results))
        except Exception as exc:
            logger.warning("NASAA fetch failed: %s", exc)

    # --- NAIC (insurance) ---
    if not sectors or "insurance" in sectors:
        try:
            naic_results = naic.fetch(since_days=since_days)
            raw_filings.extend(naic_results)
            logger.info("NAIC: fetched %d entries", len(naic_results))
        except Exception as exc:
            logger.warning("NAIC fetch failed: %s", exc)

    # --- CSBS (banking — financial_services) ---
    if not sectors or "financial_services" in sectors:
        try:
            csbs_results = csbs.fetch(since_days=since_days)
            raw_filings.extend(csbs_results)
            logger.info("CSBS: fetched %d entries", len(csbs_results))
        except Exception as exc:
            logger.warning("CSBS fetch failed: %s", exc)

    # De-duplicate and normalise
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
            logger.debug("Skipping malformed state filing %s: %s", fid, exc)

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

    # Jurisdiction
    jurisdiction_str = raw.get("jurisdiction", "federal")
    try:
        jurisdiction = Jurisdiction(jurisdiction_str)
    except ValueError:
        jurisdiction = Jurisdiction.FEDERAL

    # State code (optional)
    state_code: StateCode | None = None
    sc_raw = raw.get("state_code")
    if sc_raw:
        try:
            state_code = StateCode(sc_raw)
        except ValueError:
            pass

    return RegulatoryFiling(
        id=raw["id"],
        title=raw.get("title", raw["id"]),
        domain=domain,
        source_url=raw.get("source_url", ""),
        published_date=pub_date,
        change_type=change_type,
        raw_text=raw.get("raw_text", ""),
        jurisdiction=jurisdiction,
        state_code=state_code,
        industry_sectors=raw.get("industry_sectors", []),
    )
