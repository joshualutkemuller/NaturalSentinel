"""NASAA (North American Securities Administrators Association) fetcher.

Fetches regulatory news and enforcement actions from NASAA's website.
NASAA is the umbrella body for US state securities regulators; its releases
are tagged as IndustrySector.FINANCIAL_SERVICES and parsed for state mentions.

Source: https://www.nasaa.org/industry-resources/
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime

from app.naturalsentinel.fetchers.live.parsers import (
    detect_change_type,
    normalise_whitespace,
)

logger = logging.getLogger(__name__)

_NASAA_RSS = "https://www.nasaa.org/feed/"

# Two-letter state codes for mention extraction from press release text
_STATE_PATTERN = re.compile(
    r"\b(Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|"
    r"Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|"
    r"Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|"
    r"Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|"
    r"North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|"
    r"South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|"
    r"Wisconsin|Wyoming|District of Columbia)\b",
    re.IGNORECASE,
)

_STATE_NAME_TO_CODE: dict[str, str] = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
}


def fetch(
    since_days: int = 14,
    state_codes: list[str] | None = None,
) -> list[dict]:
    """Fetch NASAA regulatory news entries.

    Args:
        since_days: Look-back window in days (default 14).
        state_codes: Optional filter — only return entries mentioning these
            states.  ``None`` = return all entries.

    Returns:
        List of raw filing dicts tagged with ``financial_services`` sector.
    """
    import time as time_module
    from datetime import UTC, datetime, timedelta

    import feedparser

    cutoff = datetime.now(UTC) - timedelta(days=since_days)

    try:
        feed = feedparser.parse(_NASAA_RSS)
    except Exception as exc:
        logger.warning("NASAA RSS parse failed: %s", exc)
        return []

    results: list[dict] = []
    for entry in feed.get("entries", []):
        pub = _parse_date(entry, time_module)
        if pub < cutoff:
            continue

        title = normalise_whitespace(entry.get("title", ""))
        link = entry.get("link", "")
        summary = normalise_whitespace(
            re.sub(r"<[^>]+>", " ", entry.get("summary", "") or "")
        )
        text = title + " " + summary

        # Extract mentioned states
        mentioned = [
            _STATE_NAME_TO_CODE[m.lower()]
            for m in _STATE_PATTERN.findall(text)
            if m.lower() in _STATE_NAME_TO_CODE
        ]
        mentioned = list(dict.fromkeys(mentioned))  # deduplicate, preserve order

        if state_codes and not any(s in state_codes for s in mentioned):
            continue

        slug = re.sub(r"[^a-z0-9]", "", (link or title).lower())[:40]
        doc_id = f"NASAA-{hashlib.md5(slug.encode()).hexdigest()[:8].upper()}"
        change_type = detect_change_type(title + " " + summary)

        results.append(
            {
                "id": doc_id,
                "title": title,
                "domain": "state_securities",
                "source_url": link,
                "published_date": pub.strftime("%Y-%m-%d"),
                "change_type": change_type,
                "raw_text": summary or title,
                "state_code": mentioned[0] if mentioned else None,
                "industry_sectors": ["financial_services"],
                "jurisdiction": "state",
                "agency": "NASAA",
                "mentioned_states": mentioned,
            }
        )

    return results


def _parse_date(entry, time_module) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        ts = getattr(entry, attr, None)
        if ts:
            try:
                return datetime.fromtimestamp(time_module.mktime(ts), tz=UTC)
            except (OverflowError, OSError):
                pass
    return datetime.now(UTC)
