"""FINRA regulatory notices fetcher.

Scrapes FINRA's regulatory notices listing (finra.org/rules-guidance/notices)
for recent notices relevant to broker-dealers, securities lending, margin,
prime brokerage, and related business lines.

FINRA does not provide a structured JSON API for regulatory notices, so this
module parses the HTML listing and optionally fetches individual notice pages
for full text.

Source: https://www.finra.org/rules-guidance/notices
"""

from __future__ import annotations

import logging
import re
import urllib.error
from datetime import datetime, timedelta

from naturalsentinel.fetchers.live.http_client import HTTPClient
from naturalsentinel.fetchers.live.parsers import (
    detect_change_type,
    html_to_text,
    normalise_whitespace,
    truncate,
)

logger = logging.getLogger(__name__)

_FINRA_BASE = "https://www.finra.org"
_NOTICES_URL = "https://www.finra.org/rules-guidance/notices"


def fetch(
    since_days: int = 60,
    limit: int = 20,
    fetch_full_text: bool = True,
    client: HTTPClient | None = None,
) -> list[dict]:
    """Fetch recent FINRA regulatory notices.

    Args:
        since_days: Look-back window in days (default 60).
        limit: Maximum documents to return (default 20).
        fetch_full_text: Fetch and extract the text of each individual notice.
        client: Optional injected :class:`HTTPClient` (for testing).

    Returns:
        List of raw filing dicts for normalisation into
        :class:`~naturalsentinel.models.RegulatoryFiling`.
    """
    http = client or HTTPClient()

    try:
        index_html = http.get(_NOTICES_URL)
    except urllib.error.URLError as exc:
        logger.warning("FINRA regulatory notices page unavailable: %s", exc)
        return []

    cutoff = datetime.utcnow() - timedelta(days=since_days)
    entries = _parse_index(index_html, cutoff, limit)

    results: list[dict] = []
    for entry in entries:
        if fetch_full_text and entry.get("notice_url"):
            try:
                notice_html = http.get(entry["notice_url"])
                full_text = html_to_text(notice_html)
                if len(full_text) > len(entry.get("raw_text", "")):
                    entry["raw_text"] = truncate(full_text)
            except Exception as exc:
                logger.debug("Could not fetch FINRA notice text for %s: %s", entry["id"], exc)
        results.append(entry)

    return results


def _parse_index(html_content: str, cutoff: datetime, limit: int) -> list[dict]:
    """Extract notice entries from the FINRA regulatory notices listing.

    FINRA's notices page renders entries that typically include a notice number
    (e.g. "24-12"), a publication date, and a title link.  The exact HTML
    structure varies across page redesigns; we use flexible patterns.
    """
    entries: list[dict] = []

    # Pattern 1: look for FINRA notice number references (e.g. "24-15", "25-03")
    _notice_pattern = re.compile(
        r'"(/rules-guidance/notices/(\d{2}-\d+))"'  # relative URL + notice ID
        r"[^>]*>[^<]*</a>",
        re.DOTALL,
    )

    # Pattern 2: extract titles linked from the notices page
    link_pattern = re.compile(
        r'href="(/rules-guidance/notices/\d{2}-\d+)"[^>]*>\s*([^<]{10,200})\s*</a>',
        re.DOTALL,
    )

    # Date pattern anywhere near a match
    date_pattern = re.compile(
        r"(\w+\s+\d{1,2},\s+\d{4})"  # e.g. "March 15, 2026"
    )

    # Extract all links first
    links_found: list[tuple[str, str]] = []  # (rel_url, raw_title)
    for m in link_pattern.finditer(html_content):
        rel_url = m.group(1).strip()
        raw_title = normalise_whitespace(m.group(2))
        if raw_title and len(raw_title) > 8:
            links_found.append((rel_url, raw_title))

    # Find all dates in the page (approximate association)
    all_dates = date_pattern.findall(html_content)
    _date_iter = iter(all_dates)

    for rel_url, title in links_found:
        if len(entries) >= limit:
            break

        # Try to match a date from the page (approximate — positional proximity)
        pub_date = None
        for raw_date in all_dates:
            try:
                pub_date = datetime.strptime(raw_date, "%B %d, %Y")
                break
            except ValueError:
                try:
                    pub_date = datetime.strptime(raw_date, "%b %d, %Y")
                    break
                except ValueError:
                    continue

        # Default to today if no date found
        if pub_date is None:
            pub_date = datetime.utcnow()

        if pub_date < cutoff:
            continue

        # Extract notice number from URL (e.g. /rules-guidance/notices/24-15)
        notice_match = re.search(r"/(\d{2}-\d+)$", rel_url)
        notice_num = notice_match.group(1) if notice_match else rel_url.split("/")[-1]
        doc_id = f"FINRA-{notice_num}"

        notice_url = _FINRA_BASE + rel_url
        change_type = detect_change_type(title)

        entries.append(
            {
                "id": doc_id,
                "title": title,
                "domain": "finra",
                "source_url": notice_url,
                "published_date": pub_date.strftime("%Y-%m-%d"),
                "change_type": change_type,
                "raw_text": title,  # Replaced by full text if fetched
                "notice_url": notice_url,
            }
        )

    return entries
