"""State agency RSS/Atom feed fetcher.

Reads state regulatory agency RSS/Atom feeds registered in
``state_domains.STATE_AGENCY_RSS_FEEDS`` and normalises entries into
raw filing dicts.

Uses ``feedparser`` (added to pyproject.toml) for robust RSS/Atom parsing.
Falls back gracefully on a per-feed basis if the URL is unreachable.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime, timedelta

from app.naturalsentinel.fetchers.live.parsers import (
    detect_change_type,
    normalise_whitespace,
)

logger = logging.getLogger(__name__)


def fetch(
    state_codes: list[str] | None = None,
    sectors: list[str] | None = None,
    since_days: int = 7,
) -> list[dict]:
    """Fetch filings from state agency RSS/Atom feeds.

    Args:
        state_codes: Optional list of two-letter state codes to include.
            ``None`` = use all states registered in ``STATE_AGENCY_RSS_FEEDS``.
        sectors: Optional sector filter — only feeds tagged with these sectors
            are fetched.  ``None`` = fetch all sectors.
        since_days: Look-back window in days (default 7).

    Returns:
        List of raw filing dicts.
    """
    import feedparser  # lazy import — feedparser is optional

    from app.naturalsentinel.fetchers.state_domains import STATE_AGENCY_RSS_FEEDS

    cutoff = datetime.now(UTC) - timedelta(days=since_days)
    results: list[dict] = []

    states_to_fetch = state_codes or list(STATE_AGENCY_RSS_FEEDS.keys())

    for state in states_to_fetch:
        feeds = STATE_AGENCY_RSS_FEEDS.get(state.upper(), [])
        for feed_cfg in feeds:
            feed_sector = feed_cfg.get("sector", "")
            if sectors and feed_sector not in sectors:
                continue
            url: str = feed_cfg["url"]
            agency: str = feed_cfg.get("agency", state)
            try:
                entries = _parse_feed(
                    feedparser, url, state.upper(), feed_sector, agency, cutoff
                )
                results.extend(entries)
                logger.info(
                    "RSS %s (%s): fetched %d entries", agency, state, len(entries)
                )
            except Exception as exc:
                logger.warning("RSS feed failed for %s/%s: %s", state, agency, exc)

    # Apply sector filter if provided
    if sectors:
        results = [r for r in results if r.get("industry_sectors", [""])[0] in sectors]

    return results


def _parse_feed(
    feedparser,
    url: str,
    state: str,
    sector: str,
    agency: str,
    cutoff: datetime,
) -> list[dict]:
    """Parse a single RSS/Atom feed URL and return normalised filing dicts."""
    feed = feedparser.parse(url)

    if feed.get("bozo") and not feed.get("entries"):
        exc = feed.get("bozo_exception")
        raise RuntimeError(f"feedparser parse error: {exc}")

    filings: list[dict] = []
    for entry in feed.get("entries", []):
        pub = _parse_entry_date(entry)
        if pub < cutoff:
            continue

        title = normalise_whitespace(entry.get("title", ""))
        link = entry.get("link", "")
        summary = normalise_whitespace(
            _strip_html(
                entry.get("summary", "")
                or entry.get("content", [{}])[0].get("value", "")
            )
        )

        # Stable ID: hash of state + link (avoids collisions if URL changes)
        slug = re.sub(r"[^a-z0-9]", "", (link or title).lower())[:40]
        doc_id = f"SRSS-{state}-{hashlib.md5(slug.encode()).hexdigest()[:8].upper()}"

        change_type = detect_change_type(title + " " + summary)

        filings.append(
            {
                "id": doc_id,
                "title": f"[{state}] {title}",
                "domain": f"state_{sector}",
                "source_url": link,
                "published_date": pub.strftime("%Y-%m-%d"),
                "change_type": change_type,
                "raw_text": summary or title,
                "state_code": state,
                "industry_sectors": [sector],
                "jurisdiction": "state",
                "agency": agency,
            }
        )

    return filings


def _parse_entry_date(entry) -> datetime:
    """Extract a timezone-aware datetime from a feedparser entry."""
    import time as time_module

    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        ts = getattr(entry, attr, None)
        if ts:
            try:
                return datetime.fromtimestamp(time_module.mktime(ts), tz=UTC)
            except (OverflowError, OSError):
                pass
    return datetime.now(UTC)


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", " ", text)
