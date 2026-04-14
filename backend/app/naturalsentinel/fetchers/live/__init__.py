"""Live regulatory filing ingestion from public web sources.

Phase R extras E grouped the per-source fetchers into two subpackages:

- ``federal/`` — Federal Register, EDGAR, BIS, FINRA
- ``state/``   — Open States, state RSS, NASAA, NAIC, CSBS

The old attribute-style access (``live.bis``, ``live.csbs`` …) keeps
working because this module re-exports both subpackages' modules.

All fetchers accept an optional ``client`` kwarg for dependency injection
during testing (pass a mock HTTPClient to avoid live network calls).
"""

from app.naturalsentinel.fetchers.live.federal import (
    bis,
    edgar,
    federal_register,
    finra,
)
from app.naturalsentinel.fetchers.live.http_client import HTTPClient
from app.naturalsentinel.fetchers.live.parsers import (
    detect_change_type,
    html_to_text,
    normalise_whitespace,
    truncate,
)
from app.naturalsentinel.fetchers.live.state import (
    csbs,
    naic,
    nasaa,
    open_states,
    state_rss,
)

__all__ = [
    "HTTPClient",
    "bis",
    "csbs",
    "detect_change_type",
    "edgar",
    "federal_register",
    "finra",
    "html_to_text",
    "naic",
    "nasaa",
    "normalise_whitespace",
    "open_states",
    "state_rss",
    "truncate",
]
