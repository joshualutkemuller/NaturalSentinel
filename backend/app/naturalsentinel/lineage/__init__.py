"""Data lineage and explainability artifacts for NaturalSentinel.

Modules
-------
citation    FieldCitation / CitationBundle — source passages that support
            each extracted field value, parsed from the LLM response.
trace       DecisionTrace / TraceStep — step-by-step pipeline execution
            record with timing, token usage, and status per step.
provenance  ModelProvenance — provider / model / version record per step,
            enabling reproducibility and drift attribution.
"""

from app.naturalsentinel.lineage.citation import (
    CITABLE_FIELDS,
    CitationBundle,
    FieldCitation,
    parse_citations,
)
from app.naturalsentinel.lineage.provenance import ModelProvenance
from app.naturalsentinel.lineage.trace import (
    DecisionTrace,
    TraceStep,
)

__all__ = [
    # Citation
    "FieldCitation",
    "CitationBundle",
    "parse_citations",
    "CITABLE_FIELDS",
    # Trace
    "TraceStep",
    "DecisionTrace",
    # Provenance
    "ModelProvenance",
]
