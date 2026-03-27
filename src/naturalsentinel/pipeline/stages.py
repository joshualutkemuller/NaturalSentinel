"""Five-stage regulatory artifact processing pipeline.

Production pattern — treat regulatory artifact processing like data ingestion,
not prompting:

    Stage 1  Classification   what is this? which topic? complexity 1-5?
    Stage 2  Decomposition    split if complex (conditional on Stage 1)
    Stage 3  Extraction       schema-imposed pull against a per-topic template
    Stage 4  Validation       type/plausibility checks; LLM correction loop
    Stage 5  Span grounding   map extracted values → verbatim source spans

Each stage:
  - Has a clear input/output contract (dataclasses, not dicts)
  - Can be run independently for testing
  - Uses temperature=0.0 for deterministic stages (classify, decompose, validate, ground)
    and temperature=0.1 for extraction
  - Fails gracefully to a safe fallback rather than raising exceptions

FilingPipeline chains all five stages and exposes a single .run(filing) method.
"""

from __future__ import annotations

import dataclasses
import json
import re
from typing import Any

from naturalsentinel.utils.parsing import parse_llm_json

# ── Data transfer objects ────────────────────────────────────────────────────


@dataclasses.dataclass
class ClassificationResult:
    """Output of Stage 1."""

    doc_type: str  # proposed_rule | final_rule | guidance | notice | enforcement | amendment | speech
    primary_topic: str  # capital | liquidity | reporting | derivatives | model_risk | consumer_protection | market_structure | resolution | other
    complexity: int  # 1-5  (1=simple notice, 5=multi-provision final rule)
    requires_decomposition: bool
    regulatory_body: (
        str  # FED | OCC | FDIC | SEC | CFTC | CFPB | FHFA | BASEL | FSB | OTHER
    )
    confidence: float
    raw: dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class DocumentSection:
    """One logical section produced by Stage 2."""

    section_type: str  # preamble | amendments | effective_dates | definitions | supplementary | background | transition_provisions
    title: str
    text: str
    relevance_score: float  # 0-1


@dataclasses.dataclass
class ValidationResult:
    """Output of Stage 4."""

    valid: bool
    issues: list[str]
    corrected: dict  # corrected extraction (may equal the original if no issues)


@dataclasses.dataclass
class SpanGround:
    """One field-to-span mapping from Stage 5."""

    field: str
    value: Any
    source_span: str  # verbatim quote from source text (or "" if not found)
    confidence: float


@dataclasses.dataclass
class PipelineResult:
    """Aggregate output of all five stages."""

    classification: ClassificationResult
    sections: list[DocumentSection]  # empty if Stage 2 was skipped
    extracted: dict  # raw Stage 3 output
    validation: ValidationResult  # Stage 4 output
    grounding: list[SpanGround]  # Stage 5 output (may be empty)
    source_text: str

    @property
    def data(self) -> dict:
        """Canonical output: the validated (or corrected) extraction."""
        return (
            self.validation.corrected if self.validation.corrected else self.extracted
        )


# ── Per-topic extraction schemas ─────────────────────────────────────────────

EXTRACTION_SCHEMAS: dict[str, dict] = {
    "capital": {
        "rwa_impact_direction": "increase|decrease|neutral|unknown",
        "rwa_pct_change_estimate": "float (basis points, 0 if unknown)",
        "slr_impact_direction": "increase|decrease|neutral|unknown",
        "output_floor_relevance": "bool",
        "affected_capital_metrics": "list[str] — e.g. ['CET1', 'T1 leverage', 'SLR']",
        "model_recalibration_required": "bool",
        "compliance_deadline": "ISO-8601 date string or null",
        "action_items": "list[str]",
        "confidence": "float 0-1",
        "summary": "str",
    },
    "liquidity": {
        "lcr_impact_direction": "increase|decrease|neutral|unknown",
        "nsfr_impact_direction": "increase|decrease|neutral|unknown",
        "hqla_classification_changes": "list[str]",
        "funding_cost_impact_bps": "float",
        "compliance_deadline": "ISO-8601 date string or null",
        "action_items": "list[str]",
        "confidence": "float 0-1",
        "summary": "str",
    },
    "derivatives": {
        "ead_impact_direction": "increase|decrease|neutral|unknown",
        "initial_margin_change_pct": "float",
        "cva_capital_impact_bps": "float",
        "netting_set_changes": "list[str]",
        "compliance_deadline": "ISO-8601 date string or null",
        "action_items": "list[str]",
        "confidence": "float 0-1",
        "summary": "str",
    },
    "reporting": {
        "new_reporting_obligations": "list[str]",
        "changed_reporting_schedules": "list[str]",
        "schema_changes": "list[str]",
        "estimated_build_effort": "str — e.g. '3-6 months'",
        "compliance_deadline": "ISO-8601 date string or null",
        "action_items": "list[str]",
        "confidence": "float 0-1",
        "summary": "str",
    },
    "model_risk": {
        "models_requiring_revalidation": "list[str]",
        "validation_standard_changes": "list[str]",
        "sr11_7_implications": "str",
        "remediation_timeline": "str",
        "compliance_deadline": "ISO-8601 date string or null",
        "action_items": "list[str]",
        "confidence": "float 0-1",
        "summary": "str",
    },
    "resolution": {
        "tlac_mrel_changes": "list[str]",
        "resolution_plan_updates_required": "bool",
        "bail_in_mechanics_changes": "list[str]",
        "gone_concern_capital_impact_bps": "float",
        "compliance_deadline": "ISO-8601 date string or null",
        "action_items": "list[str]",
        "confidence": "float 0-1",
        "summary": "str",
    },
}

# Fallback schema for topics not in EXTRACTION_SCHEMAS
_DEFAULT_SCHEMA: dict = {
    "change_type": "proposed_rule|final_rule|guidance|notice|amendment",
    "severity": "low|medium|high|critical",
    "affected_business_lines": "list[str]",
    "affected_regulations": "list[str]",
    "compliance_deadline": "ISO-8601 date string or null",
    "action_items": "list[str]",
    "confidence": "float 0-1",
    "summary": "str",
}


# ── Stage 1 — Classification ─────────────────────────────────────────────────

_CLASSIFY_SYSTEM = """\
You are a regulatory document classifier.  Given a regulatory artifact, output \
a classification JSON object.

Output JSON only — no markdown fences, no prose outside the JSON.

Schema:
{
  "doc_type": "<proposed_rule|final_rule|guidance|enforcement|notice|amendment|executive_order|speech>",
  "primary_topic": "<capital|liquidity|reporting|derivatives|model_risk|consumer_protection|market_structure|resolution|other>",
  "complexity": <int 1-5>,
  "requires_decomposition": <bool — true if complexity >= 4 or document has multiple independent provisions>,
  "regulatory_body": "<FED|OCC|FDIC|SEC|CFTC|CFPB|FHFA|BASEL|FSB|OTHER>",
  "confidence": <float 0-1>
}
"""

_CLASSIFY_USER = """\
TITLE: {title}
DOMAIN: {domain}
PUBLISHED: {published_date}

--- BEGIN TEXT (first 1 500 chars) ---
{text_head}
--- END TEXT ---

Classify this document.
"""


class ClassificationStage:
    """Stage 1: classify the artifact's type, topic, and complexity."""

    def run(self, llm: Any, filing: dict) -> ClassificationResult:
        text = filing.get("raw_text", "") or ""
        user = _CLASSIFY_USER.format(
            title=filing.get("title", ""),
            domain=filing.get("domain", ""),
            published_date=filing.get("published_date", ""),
            text_head=text[:1500],
        )
        fallback = {
            "doc_type": "notice",
            "primary_topic": "other",
            "complexity": 2,
            "requires_decomposition": False,
            "regulatory_body": "OTHER",
            "confidence": 0.5,
        }
        raw = llm.complete(system=_CLASSIFY_SYSTEM, user=user, temperature=0.0)
        parsed = parse_llm_json(raw, fallback=fallback)
        return ClassificationResult(
            doc_type=str(parsed.get("doc_type", "notice")),
            primary_topic=str(parsed.get("primary_topic", "other")),
            complexity=int(parsed.get("complexity", 2)),
            requires_decomposition=bool(parsed.get("requires_decomposition", False)),
            regulatory_body=str(parsed.get("regulatory_body", "OTHER")),
            confidence=float(parsed.get("confidence", 0.5)),
            raw=parsed,
        )


# ── Stage 2 — Decomposition ──────────────────────────────────────────────────

_DECOMPOSE_SYSTEM = """\
You are a regulatory document analyst.  Split the provided text into its \
logical sections for parallel downstream extraction.

Output JSON only — no markdown fences.

Schema:
{
  "sections": [
    {
      "section_type": "<preamble|amendments|effective_dates|definitions|supplementary|background|transition_provisions>",
      "title": "<short section title>",
      "text": "<verbatim or condensed text>",
      "relevance_score": <float 0-1>
    }
  ]
}

Order sections by relevance_score descending.  Keep each text verbatim where \
possible; condense only if the section exceeds 800 words.
"""

_DECOMPOSE_USER = """\
DOCUMENT TYPE: {doc_type}
PRIMARY TOPIC: {primary_topic}

--- BEGIN FULL TEXT ---
{full_text}
--- END FULL TEXT ---

Split this document into its logical sections.
"""


class DecompositionStage:
    """
    Stage 2: split complex artifacts into logical sections.

    Only executes when classification.requires_decomposition is True.
    """

    def run(
        self,
        llm: Any,
        filing: dict,
        classification: ClassificationResult,
    ) -> list[DocumentSection]:
        if not classification.requires_decomposition:
            return []

        user = _DECOMPOSE_USER.format(
            doc_type=classification.doc_type,
            primary_topic=classification.primary_topic,
            full_text=(filing.get("raw_text", "") or "")[:6000],
        )
        fallback: dict = {"sections": []}
        raw = llm.complete(system=_DECOMPOSE_SYSTEM, user=user, temperature=0.0)
        parsed = parse_llm_json(raw, fallback=fallback)
        return [
            DocumentSection(
                section_type=str(s.get("section_type", "other")),
                title=str(s.get("title", "")),
                text=str(s.get("text", "")),
                relevance_score=float(s.get("relevance_score", 0.5)),
            )
            for s in parsed.get("sections", [])
        ]


# ── Stage 3 — Extraction ─────────────────────────────────────────────────────

_EXTRACT_SYSTEM = """\
You are a senior regulatory analyst performing structured data extraction.

Rules:
- Extract all fields listed in OUTPUT SCHEMA from the provided text.
- Output JSON only — no markdown fences, no prose.
- If a value cannot be determined from the text, use null (not "unknown").
- String values: concise, < 120 chars each.
- List items: 3-7 items per list maximum.
- confidence: your overall confidence in the extraction (0-1).
"""

_EXTRACT_USER = """\
DOCUMENT TYPE: {doc_type}
PRIMARY TOPIC: {primary_topic}
REGULATORY BODY: {regulatory_body}
FILING ID: {filing_id}

TEXT TO EXTRACT FROM:
---
{text}
---

OUTPUT SCHEMA (extract these fields exactly):
{schema_json}

Respond with a JSON object containing all schema fields.
"""


class ExtractionStage:
    """Stage 3: schema-imposed structured extraction."""

    def run(
        self,
        llm: Any,
        filing: dict,
        classification: ClassificationResult,
        sections: list[DocumentSection],
    ) -> dict:
        schema = EXTRACTION_SCHEMAS.get(classification.primary_topic, _DEFAULT_SCHEMA)

        # Prefer decomposed sections (highest relevance first) over raw text
        if sections:
            relevant = sorted(sections, key=lambda s: s.relevance_score, reverse=True)
            text = "\n\n".join(
                f"[{s.section_type.upper()}] {s.title}\n{s.text}" for s in relevant[:3]
            )
        else:
            text = (filing.get("raw_text") or "")[:4000]

        user = _EXTRACT_USER.format(
            doc_type=classification.doc_type,
            primary_topic=classification.primary_topic,
            regulatory_body=classification.regulatory_body,
            filing_id=filing.get("id") or filing.get("filing_id") or "",
            text=text,
            schema_json=json.dumps(schema, indent=2),
        )
        fallback = {k: None for k in schema}
        fallback["confidence"] = 0.0
        fallback["summary"] = "Extraction failed — no parseable LLM output."

        raw = llm.complete(system=_EXTRACT_SYSTEM, user=user, temperature=0.1)
        return parse_llm_json(raw, fallback=fallback)


# ── Stage 4 — Validation ─────────────────────────────────────────────────────

_REQUIRED_FIELDS = frozenset({"confidence", "summary"})
_DIRECTION_VALUES = frozenset({"increase", "decrease", "neutral", "unknown"})
_SEVERITY_VALUES = frozenset({"low", "medium", "high", "critical"})
_DOC_TYPE_VALUES = frozenset(
    {
        "proposed_rule",
        "final_rule",
        "guidance",
        "enforcement",
        "notice",
        "amendment",
        "executive_order",
        "speech",
    }
)


def _validate_field(key: str, value: Any) -> list[str]:
    if value is None:
        return []
    issues: list[str] = []
    if key.endswith("_direction") and isinstance(value, str):
        if value not in _DIRECTION_VALUES:
            issues.append(f"{key}: invalid direction '{value}'")
    if key == "severity" and isinstance(value, str):
        if value not in _SEVERITY_VALUES:
            issues.append(f"severity: invalid value '{value}'")
    if key == "doc_type" and isinstance(value, str):
        if value not in _DOC_TYPE_VALUES:
            issues.append(f"doc_type: invalid value '{value}'")
    if key == "confidence":
        try:
            v = float(value)
            if not 0.0 <= v <= 1.0:
                issues.append(f"confidence out of range: {v}")
        except (TypeError, ValueError):
            issues.append(f"confidence not numeric: {value!r}")
    if re.search(r"_pct$|_bps$|_estimate$|_impact_bps$|_change_pct$", key):
        if not isinstance(value, (int, float)):
            try:
                float(value)
            except (TypeError, ValueError):
                issues.append(
                    f"{key}: expected numeric, got {type(value).__name__} {value!r}"
                )
    return issues


_VALIDATE_SYSTEM = """\
You are a data quality validator for regulatory extraction outputs.
Given an extracted JSON object and a list of validation issues, produce a \
corrected version that resolves every issue.

Rules:
- Fix each issue listed; do not remove or rename fields.
- If a value is genuinely unfixable from context, set it to null.
- Output JSON only — no markdown, no prose.
"""

_VALIDATE_USER = """\
EXTRACTED DATA:
{extracted_json}

VALIDATION ISSUES:
{issues_text}

Return the corrected JSON object with all issues resolved.
"""


class ValidationStage:
    """
    Stage 4: validate extracted data and optionally correct via LLM.

    Runs a fast structural pass first (no LLM).  Only calls the LLM if
    validation issues are found, up to max_retries times.
    """

    def run(
        self,
        llm: Any,
        extracted: dict,
        schema: dict | None = None,
        max_retries: int = 1,
    ) -> ValidationResult:
        issues = self._check(extracted)
        if not issues:
            return ValidationResult(valid=True, issues=[], corrected=extracted)

        current = extracted
        for _ in range(max_retries):
            user = _VALIDATE_USER.format(
                extracted_json=json.dumps(current, indent=2),
                issues_text="\n".join(f"- {i}" for i in issues),
            )
            raw = llm.complete(system=_VALIDATE_SYSTEM, user=user, temperature=0.0)
            corrected = parse_llm_json(raw, fallback=current)
            remaining = self._check(corrected)
            if not remaining:
                return ValidationResult(valid=True, issues=issues, corrected=corrected)
            issues = remaining
            current = corrected

        return ValidationResult(valid=False, issues=issues, corrected=current)

    @staticmethod
    def _check(data: dict) -> list[str]:
        issues: list[str] = []
        for key in _REQUIRED_FIELDS:
            if key not in data or data[key] is None:
                issues.append(f"Missing required field: '{key}'")
        for key, value in data.items():
            issues.extend(_validate_field(key, value))
        return issues


# ── Stage 5 — Span grounding ─────────────────────────────────────────────────

_GROUND_SYSTEM = """\
You are a span-grounding expert.  For each field in the extraction, locate the \
verbatim text span from the source document that best supports the extracted value.

Output JSON only — no markdown fences.

Schema:
{
  "grounds": [
    {
      "field": "<field_name>",
      "value": <extracted value>,
      "source_span": "<verbatim quote, max 200 chars, or null if not found>",
      "confidence": <float 0-1>
    }
  ]
}

Rules:
- Only include fields with non-null values.
- source_span must be a direct quote from the source text; do not paraphrase.
- If no supporting span can be found, set source_span to null and confidence to 0.0.
"""

_GROUND_USER = """\
SOURCE TEXT:
---
{source_text}
---

EXTRACTED FIELDS:
{fields_json}

Find the source span for each field.
"""


class GroundingStage:
    """Stage 5: map each extracted value back to a verbatim source text span."""

    def run(
        self,
        llm: Any,
        extracted: dict,
        source_text: str,
        fields_to_ground: list[str] | None = None,
    ) -> list[SpanGround]:
        if fields_to_ground is None:
            fields_to_ground = [
                k
                for k, v in extracted.items()
                if v is not None
                and isinstance(v, (str, int, float))
                and k not in ("confidence", "summary")
            ]
        if not fields_to_ground:
            return []

        subset = {k: extracted[k] for k in fields_to_ground if k in extracted}
        user = _GROUND_USER.format(
            source_text=source_text[:4000],
            fields_json=json.dumps(subset, indent=2),
        )
        fallback: dict = {"grounds": []}
        raw = llm.complete(system=_GROUND_SYSTEM, user=user, temperature=0.0)
        parsed = parse_llm_json(raw, fallback=fallback)
        return [
            SpanGround(
                field=str(g.get("field", "")),
                value=g.get("value"),
                source_span=str(g.get("source_span") or ""),
                confidence=float(g.get("confidence", 0.0)),
            )
            for g in parsed.get("grounds", [])
        ]


# ── FilingPipeline — orchestrates all five stages ────────────────────────────


class FilingPipeline:
    """
    Five-stage data ingestion pipeline for a single regulatory filing.

    Analogous to a typed ETL pipeline:

        filing dict
            │
            ▼ Stage 1: ClassificationStage
        ClassificationResult  ──────────────────────────► primary_topic → schema
            │
            ▼ Stage 2: DecompositionStage  (conditional on complexity)
        list[DocumentSection]
            │
            ▼ Stage 3: ExtractionStage
        extracted dict  (against per-topic schema)
            │
            ▼ Stage 4: ValidationStage
        ValidationResult  (corrected dict)
            │
            ▼ Stage 5: GroundingStage  (optional)
        list[SpanGround]
            │
            ▼
        PipelineResult.data  ← canonical validated extraction

    Usage::

        from naturalsentinel.pipeline import FilingPipeline
        from naturalsentinel.providers.anthropic import AnthropicProvider

        llm = AnthropicProvider(model="claude-opus-4-6")
        pipeline = FilingPipeline(llm, run_grounding=True)
        result = pipeline.run(filing_dict)

        print(result.classification.primary_topic)
        print(result.data)
        for g in result.grounding:
            print(f"{g.field}: '{g.source_span}' ({g.confidence:.0%})")
    """

    def __init__(
        self,
        llm: Any,
        run_decomposition: bool = True,
        run_grounding: bool = False,
        max_validation_retries: int = 1,
    ) -> None:
        self.llm = llm
        self.run_decomposition = run_decomposition
        self.run_grounding = run_grounding
        self.max_validation_retries = max_validation_retries
        self._stage1 = ClassificationStage()
        self._stage2 = DecompositionStage()
        self._stage3 = ExtractionStage()
        self._stage4 = ValidationStage()
        self._stage5 = GroundingStage()

    def run(self, filing: dict) -> PipelineResult:
        # Stage 1
        classification = self._stage1.run(self.llm, filing)

        # Stage 2 (conditional)
        sections: list[DocumentSection] = []
        if self.run_decomposition and classification.requires_decomposition:
            sections = self._stage2.run(self.llm, filing, classification)

        # Stage 3
        extracted = self._stage3.run(self.llm, filing, classification, sections)

        # Stage 4
        schema = EXTRACTION_SCHEMAS.get(classification.primary_topic)
        validation = self._stage4.run(
            self.llm,
            extracted,
            schema,
            max_retries=self.max_validation_retries,
        )

        # Stage 5 (optional)
        grounds: list[SpanGround] = []
        if self.run_grounding:
            grounds = self._stage5.run(
                self.llm,
                validation.corrected,
                filing.get("raw_text", ""),
            )

        return PipelineResult(
            classification=classification,
            sections=sections,
            extracted=extracted,
            validation=validation,
            grounding=grounds,
            source_text=filing.get("raw_text", ""),
        )
