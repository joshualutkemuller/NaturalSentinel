"""BIS / Basel Committee (BCBS) publications fetcher.

Scrapes the Bank for International Settlements (BIS) publication listing for
Basel Committee on Banking Supervision (BCBS) consultative documents, final
standards, and working papers.

BIS does not provide a structured JSON API for its publications, so this
module scrapes the HTML publication index and follows links to extract
the abstract/summary from individual publication pages.

Source: https://www.bis.org/bcbs/publications.htm
"""

from __future__ import annotations

import logging
import re
import urllib.error
from datetime import datetime, timedelta

from app.naturalsentinel.fetchers.live.http_client import HTTPClient
from app.naturalsentinel.fetchers.live.parsers import (
    detect_change_type,
    html_to_text,
    normalise_whitespace,
    truncate,
)

logger = logging.getLogger(__name__)

_BIS_BASE = "https://www.bis.org"
_BCBS_PUBS_URL = "https://www.bis.org/bcbs/publications.htm"


def fetch(
    since_days: int = 90,
    limit: int = 20,
    fetch_full_text: bool = True,
    client: HTTPClient | None = None,
) -> list[dict]:
    """Fetch recent BCBS publications from BIS.org.

    Args:
        since_days: Look-back window in days (default 90; BIS publishes
            less frequently than US agencies).
        limit: Maximum documents to return (default 20).
        fetch_full_text: Fetch the full text of each publication page.
        client: Optional injected :class:`HTTPClient` (for testing).

    Returns:
        List of raw filing dicts for normalisation into
        :class:`~naturalsentinel.models.RegulatoryFiling`.
    """
    http = client or HTTPClient()

    try:
        index_html = http.get(_BCBS_PUBS_URL)
    except urllib.error.URLError as exc:
        logger.warning("BIS publications page unavailable: %s", exc)
        return []

    cutoff = datetime.utcnow() - timedelta(days=since_days)
    entries = _parse_index(index_html, cutoff, limit)

    results: list[dict] = []
    for entry in entries:
        if fetch_full_text and entry.get("pub_url"):
            try:
                pub_html = http.get(entry["pub_url"])
                full_text = html_to_text(pub_html)
                if len(full_text) > len(entry.get("raw_text", "")):
                    entry["raw_text"] = truncate(full_text)
            except Exception as exc:
                logger.debug(
                    "Could not fetch BIS pub text for %s: %s", entry["id"], exc
                )
        results.append(entry)

    return results


def _parse_index(html_content: str, cutoff: datetime, limit: int) -> list[dict]:
    """Extract publication entries from the BCBS publications index HTML."""
    entries: list[dict] = []

    # BIS publication listing: each entry typically looks like:
    #   <div class="item">
    #     <span class="date">15 Mar 2026</span>
    #     <a href="/bcbs/publ/d123.htm">Title of the publication</a>
    #     <p class="pdesc">Abstract text...</p>
    #   </div>
    #
    # We use a regex approach since we can't depend on lxml/bs4.

    # Find date + link pairs
    pattern = re.compile(
        r"(\d{1,2}\s+\w+\s+\d{4})"  # date like "15 Mar 2026"
        r".*?"
        r'href="(/(?:bcbs|publ|fsi)[^"]+)"'  # relative link
        r"[^>]*>([^<]+)<",  # link text = title
        re.DOTALL,
    )

    for match in pattern.finditer(html_content):
        if len(entries) >= limit:
            break

        date_str = match.group(1).strip()
        rel_url = match.group(2).strip()
        title = normalise_whitespace(match.group(3))

        if not title or len(title) < 5:
            continue

        try:
            pub_date = datetime.strptime(date_str, "%d %b %Y")
        except ValueError:
            try:
                pub_date = datetime.strptime(date_str, "%d %B %Y")
            except ValueError:
                continue

        if pub_date < cutoff:
            continue

        pub_url = _BIS_BASE + rel_url
        # Derive a stable ID from the URL path
        slug = re.sub(r"[^a-z0-9]", "-", rel_url.lower().strip("/"))
        doc_id = f"BIS-{slug[:40]}"

        change_type = detect_change_type(title)

        entries.append(
            {
                "id": doc_id,
                "title": title,
                "domain": "basel",
                "source_url": pub_url,
                "published_date": pub_date.strftime("%Y-%m-%d"),
                "change_type": change_type,
                "raw_text": title,  # Will be overwritten if full text is fetched
                "pub_url": pub_url,
            }
        )

    return entries
