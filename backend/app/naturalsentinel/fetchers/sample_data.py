"""Thin re-exports of sample regulatory filings from ``data/samples/``.

Phase R extras D moved the canonical fixtures out of this Python module
and into ``app/naturalsentinel/data/samples/filings.json`` +
``mock_analyses.json``. This module is now a compatibility shim that
loads those JSON files lazily at import time so every legacy call site
(``from app.naturalsentinel.fetchers.sample_data import SAMPLE_FILINGS``)
keeps working unchanged.

New code should prefer::

    from app.naturalsentinel.data.samples import (
        load_sample_filings,
        load_mock_analyses,
    )
"""

from __future__ import annotations

from app.naturalsentinel.data.samples import load_mock_analyses, load_sample_filings

SAMPLE_FILINGS: list[dict] = load_sample_filings()
MOCK_ANALYSES: dict[str, dict] = load_mock_analyses()

__all__ = ["MOCK_ANALYSES", "SAMPLE_FILINGS"]
