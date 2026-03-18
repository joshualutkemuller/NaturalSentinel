"""Federal Register API fetcher.

The Federal Register (federalregister.gov) publishes all US federal
rulemaking in a structured JSON API.  This module covers:

    FED   — Federal Reserve System
    CFPB  — Consumer Financial Protection Bureau
    OCC   — Office of the Comptroller of the Currency
    FDIC  — Federal Deposit Insurance Corporation
    CFTC  — Commodity Futures Trading Commission
    SEC   — Securities and Exchange Commission
    EPA   — Environmental Protection Agency
    USTR  — Office of the US Trade Representative
    FHFA  — Federal Housing Finance Agency
    FDA   — Food and Drug Administration

API reference: https://www.federalregister.gov/developers/documentation/api/v1
"""

from __future__ import annotations

import logging
import urllib.error
from datetime import datetime, timedelta
from typing import Optional

from naturalsentinel.fetchers.live.http_client import HTTPClient
from naturalsentinel.fetchers.live.parsers import (
    html_to_text, detect_change_type, normalise_whitespace, truncate,
)

logger = logging.getLogger(__name__)

_API_BASE = "https://www.federalregister.gov/api/v1/documents.json"

# Map NaturalSentinel domain codes → Federal Register agency slugs
DOMAIN_TO_AGENCY: dict[str, str] = {
    "fed":   "federal-reserve-system",
    "cfpb":  "consumer-financial-protection-bureau",
    "occ":   "comptroller-of-the-currency",
    "fdic":  "federal-deposit-insurance-corporation",
    "cftc":  "commodity-futures-trading-commission",
    "sec":   "securities-and-exchange-commission",
    "epa":   "environmental-protection-agency",
    "ustr":  "office-of-the-united-states-trade-representative",
    "fhfa":  "federal-housing-finance-agency",
    "fda":   "food-and-drug-administration",
}

# Federal Register document type → NaturalSentinel change_type
FR_TYPE_TO_CHANGE_TYPE: dict[str, str] = {
    "Rule":                   "final_rule",
    "Proposed Rule":          "proposed_rule",
    "Notice":                 "notice",
    "Presidential Document":  "executive_order",
    "Significant Proposed Rule": "proposed_rule",
    "Interim Rule":           "amendment",
}

_FIELDS = ",".join([
    "document_number",
    "title",
    "abstract",
    "type",
    "publication_date",
    "effective_on",
    "html_url",
    "pdf_url",
    "agencies",
    "regulation_id_numbers",
])


def fetch(
    domains: list[str],
    since_days: int = 30,
    per_page: int = 20,
    fetch_full_text: bool = True,
    client: Optional[HTTPClient] = None,
) -> list[dict]:
    """Fetch recent Federal Register documents for the requested domains.

    Args:
        domains: List of NaturalSentinel domain codes (e.g. ``["fed", "sec"]``).
        since_days: Look-back window in days (default 30).
        per_page: Documents to request per domain per API call (max 1000).
        fetch_full_text: If True, fetch and extract the full HTML document
            text for each result.  Set False to use abstract only (faster).
        client: Optional injected :class:`HTTPClient` (for testing).

    Returns:
        List of raw filing dicts ready for normalisation into
        :class:`~naturalsentinel.models.RegulatoryFiling`.
    """
    http = client or HTTPClient()
    since_date = (datetime.utcnow() - timedelta(days=since_days)).strftime("%Y-%m-%d")
    today = datetime.utcnow().strftime("%Y-%m-%d")

    results: list[dict] = []
    for domain in domains:
        agency_slug = DOMAIN_TO_AGENCY.get(domain)
        if not agency_slug:
            logger.debug("No Federal Register agency slug for domain %s — skipping", domain)
            continue

        params = {
            "fields[]": _FIELDS.split(","),
            "conditions[agencies][]": agency_slug,
            "conditions[type][]": ["Rule", "Proposed Rule", "Notice"],
            "conditions[publication_date][gte]": since_date,
            "conditions[publication_date][lte]": today,
            "per_page": str(min(per_page, 1000)),
            "order": "newest",
        }

        try:
            data = http.get_json(_API_BASE, params=params)
        except (urllib.error.URLError, ValueError, KeyError) as exc:
            logger.warning("Federal Register API error for domain %s: %s", domain, exc)
            continue

        for doc in data.get("results", []):
            raw = _normalise(doc, domain, http, fetch_full_text)
            if raw:
                results.append(raw)

    return results


def _normalise(
    doc: dict,
    domain: str,
    http: HTTPClient,
    fetch_full_text: bool,
) -> Optional[dict]:
    """Convert a Federal Register API result to a NaturalSentinel filing dict."""
    doc_number = doc.get("document_number", "").strip()
    title = normalise_whitespace(doc.get("title", ""))
    if not doc_number or not title:
        return None

    abstract = normalise_whitespace(doc.get("abstract") or "")
    html_url = doc.get("html_url", "")
    pub_date = doc.get("publication_date", "")
    fr_type = doc.get("type", "")

    # Resolve change_type
    change_type = FR_TYPE_TO_CHANGE_TYPE.get(fr_type) or detect_change_type(
        f"{title} {abstract}"
    )

    # Build raw_text: start with abstract, optionally augment with full HTML
    raw_text = abstract
    if fetch_full_text and html_url:
        try:
            # Federal Register prints the full HTML document at this URL
            html_content = http.get(html_url + "?print")
            full_text = html_to_text(html_content)
            if len(full_text) > len(abstract):
                raw_text = truncate(full_text)
        except Exception as exc:
            logger.debug("Could not fetch full text for %s: %s", doc_number, exc)

    if not raw_text:
        raw_text = title

    return {
        "id": f"FR-{doc_number}",
        "title": title,
        "domain": domain,
        "source_url": html_url or f"https://www.federalregister.gov/documents/search?conditions[document_numbers][]={doc_number}",
        "published_date": pub_date,
        "change_type": change_type,
        "raw_text": raw_text,
    }
