"""CSBS (Conference of State Bank Supervisors) fetcher.

Fetches regulatory guidance, policy statements, and press releases from
CSBS's news RSS feed. All entries are tagged as IndustrySector.FINANCIAL_SERVICES.

Source: https://www.csbs.org/
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

_CSBS_RSS = "https://www.csbs.org/rss.xml"


def fetch(
    since_days: int = 14,
    state_codes: list[str] | None = None,
) -> list[dict]:
    """Fetch CSBS regulatory news and guidance.

    Args:
        since_days: Look-back window in days (default 14).
        state_codes: Unused for CSBS (national scope), kept for consistent
            interface.

    Returns:
        List of raw filing dicts tagged with ``financial_services`` sector.
    """
    import time as time_module
    from datetime import UTC, datetime, timedelta

    import feedparser

    cutoff = datetime.now(UTC) - timedelta(days=since_days)

    try:
        feed = feedparser.parse(_CSBS_RSS)
    except Exception as exc:
        logger.warning("CSBS RSS parse failed: %s", exc)
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

        slug = re.sub(r"[^a-z0-9]", "", (link or title).lower())[:40]
        doc_id = f"CSBS-{hashlib.md5(slug.encode()).hexdigest()[:8].upper()}"
        change_type = detect_change_type(title + " " + summary)

        results.append(
            {
                "id": doc_id,
                "title": title,
                "domain": "state_banking",
                "source_url": link,
                "published_date": pub.strftime("%Y-%m-%d"),
                "change_type": change_type,
                "raw_text": summary or title,
                "state_code": None,
                "industry_sectors": ["financial_services"],
                "jurisdiction": "state",
                "agency": "CSBS",
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
