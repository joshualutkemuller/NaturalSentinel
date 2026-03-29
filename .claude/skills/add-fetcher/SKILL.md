---
description: Add a new live regulatory data source fetcher for a new agency. Handles domain enum, business lines, fetcher module, and registration.
context: fork
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Add a new live regulatory fetcher.

Agency code and full name: $ARGUMENTS
(e.g., `occ "Office of the Comptroller of the Currency"`)

## Step 1 — Read existing fetchers

Read `backend/app/naturalsentinel/fetchers/live/edgar.py` and `backend/app/naturalsentinel/fetchers/base.py` to understand the pattern before writing.

## Step 2 — Add domain enum

In `backend/app/naturalsentinel/models.py`, add to `RegulatoryDomain`:
```python
class RegulatoryDomain(str, Enum):
    ...
    OCC = "occ"
```

## Step 3 — Register business lines

In `backend/app/naturalsentinel/fetchers/base.py`, add to `DOMAIN_BUSINESS_LINES`:
```python
"occ": ["banking", "national_banks", "federal_savings"],
```

## Step 4 — Create the fetcher module

Create `backend/app/naturalsentinel/fetchers/live/<agency_code>.py`.

Required return shape per filing dict:
```python
{
    "id": str,            # stable unique ID (URL hash or agency-assigned)
    "title": str,
    "domain": str,        # matches RegulatoryDomain value
    "source_url": str,
    "published_date": str,  # ISO 8601
    "change_type": str,   # ChangeType value: proposed_rule, final_rule, guidance, etc.
    "raw_text": str,      # full text or summary
}
```

Use `HTTPClient` from `fetchers/live/http_client.py` for rate-limited HTTP.
Use parsers from `fetchers/live/parsers.py` for HTML/XML extraction.

## Step 5 — Register in base.py

In `_fetch_live()` in `backend/app/naturalsentinel/fetchers/base.py`, add a block following the SEC EDGAR pattern:

```python
if "occ" in domains_to_fetch:
    try:
        from app.naturalsentinel.fetchers.live.occ import fetch as fetch_occ
        results.extend(await fetch_occ(since_days, fetch_full_text, client))
    except Exception:
        logger.warning("OCC fetcher failed", exc_info=True)
```

If it uses the Federal Register API, add to `DOMAIN_TO_AGENCY` instead of a standalone block.

## Step 6 — Expose in CLI

In `backend/app/naturalsentinel/cli.py`, add the agency code to the `--domains` help text/choices.

## Step 7 — Run tests

```bash
cd backend && uv run pytest tests/ -m "not slow" -x
```

Slow tests (`-m slow`) hit real APIs — skip unless explicitly testing the new fetcher end-to-end.
