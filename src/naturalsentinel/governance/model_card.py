"""Model Card — governance artifact documenting AI model capabilities,
limitations, intended use, and evaluation results for NaturalSentinel.

A model card is a standardised factsheet that accompanies an AI system so
regulators, auditors, and deploying teams can make informed decisions about
its appropriate use.  See Mitchell et al. (2019) for the original framework.

Usage::

    card = ModelCard.default()
    card_dict = card.to_dict()

    # Load an overriding model card from a JSON file:
    card = ModelCard.from_json("/path/to/model_card.json")

    # Quick validation:
    warnings = card.validate()
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ModelCard:
    """Governance artifact for NaturalSentinel's AI extraction pipeline.

    Fields follow the Google Model Cards standard
    (https://modelcards.withgoogle.com/).
    """

    # Identity
    name: str
    version: str
    provider: str  # LLM provider used at analysis time
    model_id: str  # Provider model identifier
    release_date: str  # ISO date of this card version
    last_reviewed: str  # ISO date of last governance review

    # Use
    intended_use: str
    intended_users: list[str]
    out_of_scope_uses: list[str]

    # Factors
    evaluated_domains: list[str]  # Regulatory domains covered
    known_limitations: list[str]
    ethical_considerations: list[str]

    # Evaluation (populated from run_evaluation output)
    evaluation_metrics: dict[str, float] = field(default_factory=dict)
    evaluation_notes: str = ""

    # Operations
    update_cadence: str = ""
    contact: str = ""
    license: str = "MIT"

    def to_dict(self) -> dict:
        return asdict(self)

    def validate(self) -> list[str]:
        """Return a list of governance warnings for missing/incomplete fields."""
        warnings: list[str] = []
        if not self.intended_use:
            warnings.append("intended_use is empty")
        if not self.known_limitations:
            warnings.append("known_limitations is empty — every model has limitations")
        if not self.out_of_scope_uses:
            warnings.append("out_of_scope_uses is empty")
        if not self.ethical_considerations:
            warnings.append("ethical_considerations is empty")
        if not self.contact:
            warnings.append("contact is missing — who owns this model card?")
        if not self.last_reviewed:
            warnings.append("last_reviewed date is missing")
        if not self.evaluation_metrics:
            warnings.append("evaluation_metrics is empty — run the evaluation skill first")
        return warnings

    @classmethod
    def from_json(cls, path: str) -> ModelCard:
        """Load a model card from a JSON file, merging with defaults."""
        with Path(path).open() as fh:
            data = json.load(fh)
        defaults = cls.default().to_dict()
        defaults.update(data)
        return cls(**{k: v for k, v in defaults.items() if k in cls.__dataclass_fields__})

    @classmethod
    def default(cls) -> ModelCard:
        """Return the canonical NaturalSentinel model card."""
        return cls(
            name="NaturalSentinel Regulatory Extraction Pipeline",
            version="1.0.0",
            provider="anthropic",
            model_id="claude-sonnet-4-6",
            release_date="2026-03-01",
            last_reviewed="2026-03-18",
            intended_use=(
                "Automated first-pass analysis of regulatory filings published by "
                "US and international financial regulators (SEC, Federal Reserve, "
                "OCC, FDIC, CFTC, CFPB, FHFA, FINRA, Basel Committee).  Extracts "
                "structured metadata — severity, affected business lines, compliance "
                "deadlines, and action items — to assist human compliance analysts, "
                "risk managers, and legal teams in prioritising their review workload."
            ),
            intended_users=[
                "Compliance officers and analysts",
                "Chief Risk Officers and risk management teams",
                "Legal and regulatory affairs functions",
                "Portfolio managers with regulatory exposure",
                "Audit and governance committees",
            ],
            out_of_scope_uses=[
                "Replacing qualified legal advice or counsel opinion",
                "Making binding compliance decisions without human review",
                "Analysing non-regulatory documents (earnings calls, news)",
                "Real-time trading decisions based on extracted severity scores",
                "Jurisdictions outside the explicitly evaluated regulatory domains",
            ],
            known_limitations=[
                "Confidence scores are probabilistic estimates — calibration should "
                "be verified regularly using the run_evaluation skill.",
                "LLM outputs can hallucinate citations or misclassify novel filing "
                "formats not represented in the curated sample data.",
                "Compliance deadlines extracted from dense regulatory text may omit "
                "phase-in provisions or carve-outs; human verification is required.",
                "Affected business-line mapping is seeded from a curated taxonomy; "
                "highly specialised business lines may be missed.",
                "Performance degrades on filings longer than ~80,000 characters due "
                "to context-window truncation.",
                "No fine-tuning has been performed; performance reflects the base "
                "model's general regulatory knowledge.",
            ],
            ethical_considerations=[
                "This system must not be used as a substitute for qualified legal "
                "advice.  All critical compliance decisions require human review.",
                "Regulatory extractions may reflect biases present in the underlying "
                "LLM's training data, particularly for under-represented jurisdictions.",
                "Audit trails (audit_log) and feedback corrections (feedback_log) "
                "must be retained to enable accountability and model improvement.",
                "Escalation policies should be configured to route critical findings "
                "to human reviewers, not to automated enforcement systems.",
                "Model card, control matrix, and evaluation reports should be shared "
                "with relevant audit and compliance stakeholders.",
            ],
            evaluated_domains=[
                "sec",
                "fed",
                "cfpb",
                "occ",
                "fdic",
                "cftc",
                "fhfa",
                "finra",
                "epa",
                "ustr",
                "fda",
                "basel",
            ],
            evaluation_metrics={},  # Populated after first evaluation run
            evaluation_notes=(
                "Run `run_evaluation` skill (mode='historical') after accumulating "
                "at least 20 human feedback corrections to populate accuracy metrics."
            ),
            update_cadence=(
                "Model card should be reviewed when the LLM provider or model "
                "version changes, when evaluation accuracy drops below 0.70, or "
                "quarterly as a minimum."
            ),
            contact="compliance-ai-team@example.com",
            license="MIT",
        )
