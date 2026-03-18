"""Source citation per extracted field.

For every field the LLM extracts (severity, change_type, compliance_deadline,
affected_business_lines, etc.) we request that it quote the verbatim passage
from the source document that supports the extraction.  These passages are
stored as :class:`FieldCitation` objects bundled into a :class:`CitationBundle`.

The :func:`parse_citations` function extracts the ``citations`` key from a
raw LLM response dict so downstream code doesn't need to know the key name.

Usage::

    raw = parse_llm_json(llm_response)
    bundle = parse_citations(raw, filing_id="SEC-001", source_url="https://...")
    sev_cit = bundle.get("severity")
    if sev_cit:
        print(sev_cit.source_passage)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


# Fields for which we request citations
CITABLE_FIELDS: frozenset[str] = frozenset({
    "severity",
    "change_type",
    "compliance_deadline",
    "affected_business_lines",
    "affected_regulations",
    "risk_summary",
})


@dataclass
class FieldCitation:
    """A source passage supporting a single extracted field value."""

    field: str              # Field name, e.g. "severity"
    value: object           # The extracted value
    source_passage: str     # Verbatim (or near-verbatim) quote from the document
    source_url: str         # URL of the originating document
    section_hint: str = ""  # Optional section/page reference, e.g. "Section II.A"
    confidence: float = 0.0 # Per-field confidence (0–1); 0.0 if not provided

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CitationBundle:
    """All field citations for a single filing analysis."""

    filing_id: str
    source_url: str
    citations: list[FieldCitation] = field(default_factory=list)
    extracted_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def get(self, field_name: str) -> Optional[FieldCitation]:
        """Return the citation for *field_name*, or None if absent."""
        for c in self.citations:
            if c.field == field_name:
                return c
        return None

    def to_dict(self) -> dict:
        return {
            "filing_id": self.filing_id,
            "source_url": self.source_url,
            "extracted_at": self.extracted_at,
            "citations": [c.to_dict() for c in self.citations],
        }

    def as_flat_dict(self) -> dict[str, str]:
        """Return {field_name: source_passage} for quick lookup."""
        return {c.field: c.source_passage for c in self.citations}


def parse_citations(
    parsed_llm_response: dict,
    filing_id: str,
    source_url: str = "",
    overall_confidence: float = 0.0,
) -> CitationBundle:
    """Extract :class:`CitationBundle` from a parsed LLM response dict.

    The LLM is instructed (via the system prompt) to include a ``"citations"``
    key mapping field names to their supporting passages.  This function reads
    that dict and builds typed :class:`FieldCitation` objects.

    If the LLM omits ``citations`` (e.g. older prompt version), an empty
    :class:`CitationBundle` is returned so callers remain forward-compatible.

    Args:
        parsed_llm_response: Dict returned by ``parse_llm_json()``.
        filing_id: ID of the filing being analysed.
        source_url: URL of the source document.
        overall_confidence: The ``confidence`` value from the top-level assessment
            (used as per-field fallback when individual confidences are absent).

    Returns:
        :class:`CitationBundle` — may be empty if the LLM did not cite.
    """
    raw_citations: dict[str, str] = parsed_llm_response.get("citations", {})
    field_confidences: dict[str, float] = parsed_llm_response.get(
        "field_confidences", {}
    )

    citations: list[FieldCitation] = []
    for field_name, passage in raw_citations.items():
        if not passage or not isinstance(passage, str):
            continue
        value = parsed_llm_response.get(field_name)
        conf = float(field_confidences.get(field_name, overall_confidence))
        citations.append(
            FieldCitation(
                field=field_name,
                value=value,
                source_passage=passage.strip(),
                source_url=source_url,
                confidence=round(conf, 4),
            )
        )

    return CitationBundle(
        filing_id=filing_id,
        source_url=source_url,
        citations=citations,
    )
