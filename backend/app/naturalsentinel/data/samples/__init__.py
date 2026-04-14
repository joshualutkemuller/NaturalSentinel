"""Sample fixture data for the built-in sample fetcher and tests.

The canonical sample filings and their pre-computed mock analyses live
as JSON files in this directory:

- ``filings.json``       — list of sample ``RegulatoryFiling``-shaped dicts
- ``mock_analyses.json`` — dict keyed by filing id → pre-built impact analysis

Moved out of ``fetchers/sample_data.py`` in Phase R extras D so that
regulatory / business ops can refresh fixtures without touching Python
code.

Fixture freshness policy (Phase P0.5)
-------------------------------------
The majority of entries use dates within the last 12 months so the
``since_days=365`` fetcher tests exercise a realistic window.
Downstream tests **do not** assert ``len(results) == len(fixtures)``
— they use ``<=`` bounds so aging a fixture out of the window is not
itself a failure.

**Do NOT delete** ``SEC-2023-0726-CYB``. It is the real SEC
Cybersecurity Risk Management Final Rule (Release Nos. 33-11216,
34-97989) and is referenced as load-bearing historical content by
the source-provenance test suite in
``tests/naturalsentinel/documents/test_document_intelligence.py``.
Fresh fixtures are added alongside it, not in place of it.
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
