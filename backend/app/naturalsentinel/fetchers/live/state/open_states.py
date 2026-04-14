"""Open States API fetcher for state legislative bills.

Calls the Open States GraphQL API (https://v3.openstates.org/graphql) to
retrieve recently-introduced bills across US states, tagged to industry sectors
via keyword matching on bill subjects and titles.

Requires the ``OPEN_STATES_API_KEY`` environment variable (free registration
at https://openstates.org/accounts/profile/).

Source: https://docs.openstates.org/api-v3/
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

from app.naturalsentinel.fetchers.live.http_client import HTTPClient

logger = logging.getLogger(__name__)

_GRAPHQL_URL = "https://v3.openstates.org/graphql"

# ---------------------------------------------------------------------------
# Keyword → sector mapping for bill subject/title classification
# ---------------------------------------------------------------------------

_SECTOR_KEYWORDS: dict[str, list[str]] = {
    "financial_services": [
        "bank",
        "banking",
        "credit",
        "lending",
        "fintech",
        "securities",
        "investment",
        "broker",
        "financial",
        "money transmission",
        "mortgage",
        "cryptocurrency",
        "digital asset",
    ],
    "insurance": [
        "insurance",
        "insurer",
        "premium",
        "reinsurance",
        "annuity",
        "life insurance",
        "health insurance",
        "property insurance",
        "casualty",
    ],
    "healthcare": [
        "health",
        "healthcare",
        "medical",
        "hospital",
        "pharmacy",
        "drug",
        "prescription",
        "medicaid",
        "medicare",
        "patient",
        "telehealth",
        "mental health",
    ],
    "energy_utilities": [
        "energy",
        "utility",
        "utilities",
        "electricity",
        "gas",
        "pipeline",
        "renewable",
        "solar",
        "wind",
        "grid",
        "rate",
        "public utility",
    ],
    "real_estate": [
        "real estate",
        "housing",
        "landlord",
        "tenant",
        "rent",
        "mortgage",
        "foreclosure",
        "zoning",
        "property",
    ],
    "technology": [
        "technology",
        "data privacy",
        "cybersecurity",
        "artificial intelligence",
        "ai",
        "software",
        "internet",
        "digital",
        "surveillance",
        "biometric",
    ],
    "manufacturing": [
        "manufacturing",
        "factory",
        "industrial",
        "worker safety",
        "osha",
        "emission",
        "pollution",
    ],
    "transportation": [
        "transportation",
        "motor vehicle",
        "trucking",
        "aviation",
        "rail",
        "transit",
        "autonomous vehicle",
        "rideshare",
    ],
}


def _classify_sectors(title: str, subjects: list[str]) -> list[str]:
    """Return a list of matching IndustrySector values based on title/subjects."""
    text = (title + " " + " ".join(subjects)).lower()
    matched: list[str] = []
    for sector, keywords in _SECTOR_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            matched.append(sector)
    return matched or ["financial_services"]  # default fallback


def fetch(
    state_codes: list[str] | None = None,
    sectors: list[str] | None = None,
    since_days: int = 7,
    limit_per_state: int = 25,
    api_key: str | None = None,
    client: HTTPClient | None = None,
) -> list[dict]:
    """Fetch recently updated state bills from the Open States API.

    Args:
        state_codes: List of two-letter state codes to query. ``None`` = all 50
            states + DC (slow; use state filter for production queries).
        sectors: Optional sector filter — only bills matching these sectors are
            returned.  ``None`` = return all classified bills.
        since_days: Look-back window for bill updates (default 7).
        limit_per_state: Max bills to return per state (default 25).
        api_key: Open States API key. Falls back to ``OPEN_STATES_API_KEY``
            environment variable.
        client: Optional injected HTTPClient (for testing).

    Returns:
        List of raw filing dicts.
    """
    import os

    key = api_key or os.environ.get("OPEN_STATES_API_KEY", "")
    if not key:
        logger.warning("OPEN_STATES_API_KEY not set — skipping Open States fetch")
        return []

    http = client or HTTPClient()
    cutoff = (datetime.now(UTC) - timedelta(days=since_days)).strftime("%Y-%m-%d")

    states_to_query = state_codes or _DEFAULT_STATES
    results: list[dict] = []

    for state in states_to_query:
        try:
            bills = _fetch_state_bills(http, key, state, cutoff, limit_per_state)
            results.extend(bills)
        except Exception as exc:
            logger.warning("Open States fetch failed for %s: %s", state, exc)

    # Apply sector filter if requested
    if sectors:
        results = [
            r
            for r in results
            if any(s in r.get("industry_sectors", []) for s in sectors)
        ]

    return results


def _fetch_state_bills(
    http: HTTPClient,
    api_key: str,
    state: str,
    since_date: str,
    limit: int,
) -> list[dict]:
    """Query Open States GraphQL for bills in a single state."""
    query = """
    query($state: String!, $since: DateTime!, $first: Int!) {
      bills(jurisdiction: $state, updatedSince: $since, first: $first,
            sort: UPDATED_AT_DESC) {
        edges {
          node {
            id
            identifier
            title
            updatedAt
            createdAt
            classification
            subjects
            abstracts { abstract }
            sources { url }
            chamber { name }
            currentAction {
              date
              description
            }
          }
        }
      }
    }
    """
    variables = {
        "state": state.lower(),
        "since": f"{since_date}T00:00:00Z",
        "first": limit,
    }
    payload = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        _GRAPHQL_URL,
        data=payload,
        headers={
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
            "User-Agent": "NaturalSentinel/1.0 regulatory-monitor",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Open States request failed: {exc}") from exc

    edges = data.get("data", {}).get("bills", {}).get("edges", [])
    filings: list[dict] = []

    for edge in edges:
        node = edge.get("node", {})
        bill_id = node.get("id", "")
        identifier = node.get("identifier", bill_id)
        title = node.get("title", "")
        subjects = node.get("subjects") or []
        sources = node.get("sources") or []
        source_url = (
            sources[0]["url"] if sources else f"https://openstates.org/bills/{bill_id}/"
        )

        # Published date: prefer currentAction.date, fall back to createdAt
        action = node.get("currentAction") or {}
        pub_date = (
            action.get("date") or node.get("createdAt") or node.get("updatedAt", "")
        )
        if pub_date:
            pub_date = pub_date[:10]  # keep YYYY-MM-DD only

        abstracts = node.get("abstracts") or []
        abstract_text = abstracts[0]["abstract"] if abstracts else ""

        sectors = _classify_sectors(title, subjects)
        action_desc = action.get("description", "")
        change_type = _classify_change_type(node.get("classification", []), action_desc)

        doc_id = (
            f"OPENSTATES-{state.upper()}-{re.sub(r'[^A-Z0-9]', '', identifier.upper())}"
        )

        filings.append(
            {
                "id": doc_id,
                "title": f"[{state.upper()}] {title}",
                "domain": "state_legislation",
                "source_url": source_url,
                "published_date": pub_date,
                "change_type": change_type,
                "raw_text": abstract_text or title,
                "state_code": state.upper(),
                "industry_sectors": sectors,
                "jurisdiction": "state",
                "bill_identifier": identifier,
                "subjects": subjects,
            }
        )

    return filings


def _classify_change_type(classifications: list[str], action_desc: str) -> str:
    """Map Open States bill classifications to our change_type vocabulary."""
    classification_str = " ".join(classifications).lower()
    action_lower = action_desc.lower()
    if (
        "signed" in action_lower
        or "enacted" in action_lower
        or "chaptered" in action_lower
    ):
        return "final_rule"
    if "passed" in action_lower or "enrolled" in action_lower:
        return "final_rule"
    if "introduced" in classification_str or "bill" in classification_str:
        return "proposed_rule"
    if "resolution" in classification_str:
        return "notice"
    return "notice"


# Default set of states to query when no filter provided.
# Full 50-state scan is available but expensive; expand as needed.
_DEFAULT_STATES = [
    "CA",
    "NY",
    "TX",
    "FL",
    "IL",
    "MA",
    "PA",
    "OH",
    "GA",
    "NC",
    "WA",
    "CO",
    "AZ",
    "NJ",
    "VA",
]
