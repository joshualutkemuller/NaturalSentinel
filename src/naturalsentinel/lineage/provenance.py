"""Model / provider / version provenance per analysis step.

:class:`ModelProvenance` captures exactly which LLM provider, model, version,
and sampling parameters were used at each step of the pipeline.  This enables:

- Reproducibility: anyone with the same model + prompt can re-run the analysis.
- Accountability: if a mistake is traced back, the responsible model version
  is on record.
- Drift attribution: when extraction patterns shift, provenance records tell
  us whether a model version change preceded the drift.

Usage::

    prov = ModelProvenance.from_context(context, prompt_template=SYSTEM_PROMPT)
    step.provider = prov.provider
    step.model = prov.model
    step.model_version = prov.model_version
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ModelProvenance:
    """Provenance record for a single pipeline step that calls the LLM."""

    provider: str               # "anthropic" | "openai" | "gemini" | "unknown"
    model: str                  # Model identifier, e.g. "claude-sonnet-4-6"
    model_version: str          # API version / date string if available
    temperature: float          # Sampling temperature used
    max_tokens: int             # Token limit configured
    prompt_template_hash: str   # SHA-256[:16] of the system prompt template
    skill_version: str = ""     # Version of the skill that invoked the LLM
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def hash_prompt(template: str) -> str:
        """Return a 16-character SHA-256 hex digest of *template*."""
        return hashlib.sha256(template.encode()).hexdigest()[:16]

    @classmethod
    def from_context(
        cls,
        context,
        prompt_template: str = "",
        skill_version: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> "ModelProvenance":
        """Build a :class:`ModelProvenance` from a :class:`SkillContext`.

        Extracts provider and model from ``context.llm`` if available, falling
        back to "unknown" so callers never need to guard against None.

        Args:
            context: :class:`~naturalsentinel.agent_framework.SkillContext`.
            prompt_template: The system prompt text (hashed, not stored verbatim).
            skill_version: Version string of the calling skill.
            temperature: Sampling temperature passed to the LLM.
            max_tokens: Token budget passed to the LLM.
        """
        provider = "unknown"
        model = "unknown"
        model_version = ""

        llm = getattr(context, "llm", None)
        if llm is not None:
            provider = getattr(llm, "provider", "unknown") or "unknown"
            model = getattr(llm, "model", "unknown") or "unknown"
            model_version = getattr(llm, "model_version", "") or ""

        return cls(
            provider=str(provider),
            model=str(model),
            model_version=str(model_version),
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_template_hash=cls.hash_prompt(prompt_template),
            skill_version=skill_version,
        )

    @classmethod
    def unknown(cls) -> "ModelProvenance":
        """Sentinel provenance for cases where the LLM was not called."""
        return cls(
            provider="unknown",
            model="unknown",
            model_version="",
            temperature=0.0,
            max_tokens=0,
            prompt_template_hash="",
        )
