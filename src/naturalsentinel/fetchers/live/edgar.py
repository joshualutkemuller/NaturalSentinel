"""SEC EDGAR full-text search fetcher.

Queries the EDGAR full-text search API (EFTS) for recent SEC regulatory
releases.  This supplements the Federal Register fetcher with SEC-specific
content that may not appear there — enforcement orders, no-action letters,
interpretive releases, and staff guidance published directly on SEC.gov.

EDGAR EFTS API: https://efts.sec.gov/LATEST/search-index
EDGAR submissions: https://data.sec.gov/submissions/CIK{:010d}.json
"""

from __future__ import annotations

import logging
import re
import urllib.error
from datetime import datetime, timedelta
from typing import Optional

from naturalsentinel.fetchers.live.http_client import HTTPClient
from naturalsentinel.fetchers.live.parsers import (
    html_to_text, detect_change_type, normalise_whitespace, truncate,
)

logger = logging.getLogger(__name__)

_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
_EDGAR_VIEWER_BASE = "https://www.sec.gov/Archives/edgar/data"

# EDGAR form types relevant to regulatory monitoring
_REGULATORY_FORM_TYPES = "34-12B,34-12G,8-A12B,DEF 14A,S-7,S-8"

# Key queries for detecting SEC regulatory actions in free-text search
_REGULATORY_QUERIES = [
    "proposed rule",
    "final rule",
    "regulatory guidance",
    "enforcement action",
]


def fetch(
    since_days: int = 30,
    per_query: int = 10,
    fetch_full_text: bool = False,
    client: Optional[HTTPClient] = None,
) -> list[dict]:
    """Fetch recent SEC regulatory filings via EDGAR full-text search.

    The EFTS API searches the full text of all SEC EDGAR filings.  We issue
    several regulatory keyword queries and de-duplicate results by accession
    number.

    Args:
        since_days: Look-back window in days (default 30).
        per_query: Maximum hits per keyword query (default 10).
        fetch_full_text: Attempt to fetch and extract the filing HTML text.
            Disabled by default because EDGAR filings vary significantly in
            structure; abstract snippet is used instead.
        client: Optional injected :class:`HTTPClient` (for testing).

    Returns:
        List of raw filing dicts keyed for normalisation into
        :class:`~naturalsentinel.models.RegulatoryFiling`.
    """
    http = client or HTTPClient()
    start_dt = (datetime.utcnow() - timedelta(days=since_days)).strftime("%Y-%m-%d")
    end_dt = datetime.utcnow().strftime("%Y-%m-%d")

    seen_accessions: set[str] = set()
    results: list[dict] = []

    for query in _REGULATORY_QUERIES:
        params = {
            "q": f'"{query}"',
            "dateRange": "custom",
            "startdt": start_dt,
            "enddt": end_dt,
            "hits.hits.total.value": "true",
        }
        try:
            data = http.get_json(_EFTS_URL, params=params)
        except (urllib.error.URLError, ValueError) as exc:
            logger.warning("EDGAR EFTS error for query '%s': %s", query, exc)
            continue

        hits = data.get("hits", {}).get("hits", [])
        for hit in hits[:per_query]:
            src = hit.get("_source", {})
            acc = src.get("accession_no", "")
            if not acc or acc in seen_accessions:
                continue
            seen_accessions.add(acc)

            raw = _normalise(hit, http, fetch_full_text)
            if raw:
                results.append(raw)

    return results


def _normalise(
    hit: dict,
    http: HTTPClient,
    fetch_full_text: bool,
) -> Optional[dict]:
    """Convert an EDGAR EFTS hit to a NaturalSentinel filing dict."""
    src = hit.get("_source", {})
    acc = src.get("accession_no", "")
    if not acc:
        return None

    # Clean accession number → filing ID
    filing_id = "EDGAR-" + acc.replace("-", "")

    title = normalise_whitespace(
        src.get("display_names", ["SEC"])[0] + ": " + src.get("file_num", acc)
    )

    file_date = src.get("file_date") or src.get("period_of_report", "")
    entity_name = src.get("entity_name", "")
    form_type = src.get("form_type", "")

    # Try to get a better title from entity + form type
    if entity_name:
        title = f"{entity_name} — {form_type or 'SEC Filing'} ({acc})"

    source_url = _build_edgar_url(src)
    raw_text = f"SEC EDGAR filing {acc}. Entity: {entity_name}. Form: {form_type}."

    if fetch_full_text and source_url:
        try:
            html_content = http.get(source_url)
            extracted = html_to_text(html_content)
            if len(extracted) > len(raw_text):
                raw_text = truncate(extracted)
        except Exception as exc:
            logger.debug("Could not fetch full text for %s: %s", acc, exc)

    change_type = detect_change_type(f"{title} {form_type}")

    return {
        "id": filing_id,
        "title": title,
        "domain": "sec",
        "source_url": source_url,
        "published_date": file_date,
        "change_type": change_type,
        "raw_text": raw_text,
    }


def _build_edgar_url(src: dict) -> str:
    """Build a viewer URL for an EDGAR filing."""
    acc = src.get("accession_no", "")
    cik = src.get("entity_id", "") or src.get("file_num", "")

    # Try to extract numeric CIK
    cik_match = re.search(r"\d+", cik or "")
    if cik_match and acc:
        cik_num = cik_match.group()
        acc_path = acc.replace("-", "")
        return f"{_EDGAR_VIEWER_BASE}/{cik_num}/{acc_path}/{acc}-index.htm"

    # Fallback to EDGAR search
    if acc:
        return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&filenum={acc}"
    return "https://www.sec.gov/cgi-bin/browse-edgar"
