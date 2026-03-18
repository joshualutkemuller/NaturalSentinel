"""Live regulatory filing ingestion from public web sources.

Sources
-------
federal_register  Federal Register API (FED, CFPB, OCC, FDIC, CFTC, SEC,
                  EPA, USTR, FHFA, FDA) — primary source for US rulemaking.
edgar             SEC EDGAR full-text search — supplementary SEC content
                  (enforcement releases, no-action letters, staff guidance).
bis               BIS / BCBS publications — Basel Committee consultative
                  documents and final standards.
finra             FINRA regulatory notices — broker-dealer, securities
                  lending, margin, and TBA/MBS guidance.

All fetchers accept an optional ``client`` kwarg for dependency injection
during testing (pass a mock HTTPClient to avoid live network calls).
"""

from naturalsentinel.fetchers.live.http_client import HTTPClient
from naturalsentinel.fetchers.live.parsers import (
    html_to_text,
    detect_change_type,
    normalise_whitespace,
    truncate,
)
from naturalsentinel.fetchers.live import federal_register, edgar, bis, finra

__all__ = [
    "HTTPClient",
    "html_to_text",
    "detect_change_type",
    "normalise_whitespace",
    "truncate",
    "federal_register",
    "edgar",
    "bis",
    "finra",
]
