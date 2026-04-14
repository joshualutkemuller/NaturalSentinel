"""Sample fixture data for the built-in sample fetcher and tests.

The canonical sample filings and their pre-computed mock analyses live
as JSON files in this directory:

- ``filings.json``       — list of sample ``RegulatoryFiling``-shaped dicts
- ``mock_analyses.json`` — dict keyed by filing id → pre-built impact analysis

Moved out of ``fetchers/sample_data.py`` in Phase R extras D so that
regulatory / business ops can refresh fixtures without touching Python
code.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).parent


@lru_cache(maxsize=1)
def load_sample_filings() -> list[dict]:
    """Return the sample regulatory filings."""
    return json.loads((_DATA_DIR / "filings.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_mock_analyses() -> dict[str, dict]:
    """Return the pre-built mock impact analyses keyed by filing id."""
    return json.loads((_DATA_DIR / "mock_analyses.json").read_text(encoding="utf-8"))


__all__ = ["load_mock_analyses", "load_sample_filings"]
