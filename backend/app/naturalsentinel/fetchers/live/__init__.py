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

from app.naturalsentinel.fetchers.live import bis, edgar, federal_register, finra
from app.naturalsentinel.fetchers.live.http_client import HTTPClient
from app.naturalsentinel.fetchers.live.parsers import (
    detect_change_type,
    html_to_text,
    normalise_whitespace,
    truncate,
)

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
