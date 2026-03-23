"""Five-stage data ingestion pipeline for regulatory artifact processing.

Treats prompt engineering as a structured ETL pipeline rather than monolithic
single-shot prompting.  Each stage is independently testable, cacheable, and
composable — analogous to a data ingestion architecture (classify → decompose
→ extract → validate → ground) rather than a single "mega-prompt".

Stages
------
1. Classification  — what is this artifact? which topic? how complex?
2. Decomposition   — split complex documents into logical sections (conditional)
3. Extraction      — schema-imposed structured pull against a per-topic schema
4. Validation      — cross-field type / plausibility checks; LLM correction loop
5. Span grounding  — map each extracted value back to a verbatim source span

Usage
-----
    from naturalsentinel.pipeline import FilingPipeline

    pipeline = FilingPipeline(llm_provider, run_grounding=True)
    result = pipeline.run(filing_dict)

    print(result.data)          # validated extraction
    print(result.classification.primary_topic)
    for g in result.grounding:
        print(g.field, "→", g.source_span)
"""

from naturalsentinel.pipeline.stages import (
    EXTRACTION_SCHEMAS,
    ClassificationResult,
    ClassificationStage,
    DecompositionStage,
    DocumentSection,
    ExtractionStage,
    FilingPipeline,
    GroundingStage,
    PipelineResult,
    SpanGround,
    ValidationResult,
    ValidationStage,
)

__all__ = [
    "ClassificationResult",
    "ClassificationStage",
    "DecompositionStage",
    "DocumentSection",
    "ExtractionStage",
    "FilingPipeline",
    "GroundingStage",
    "PipelineResult",
    "SpanGround",
    "ValidationResult",
    "ValidationStage",
    "EXTRACTION_SCHEMAS",
]
