"""Skill: Platform Antitrust Impact Analysis — map DMA/DSA gatekeeper obligations, FTC/DOJ enforcement signals, interoperability mandates, and structural remedy risks.

Designed for platform operators, Big Tech regulatory affairs teams, and M&A counsel
building compliance workflows around digital competition law. Parses a regulatory filing
for structured antitrust and competition law implications under EU and US frameworks.
"""

from app.naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)
from app.naturalsentinel.fetchers import DOMAIN_BUSINESS_LINES
from app.naturalsentinel.utils.parsing import parse_llm_json

PLATFORM_ANTITRUST_SYSTEM = """\
You are a senior digital platform competition law specialist with expertise in EU Digital \
Markets Act (DMA), Digital Services Act (DSA), FTC Section 5, DOJ Sherman Act enforcement, \
and platform self-preferencing doctrine.
Your task is to extract structured competition law impact data from a regulatory filing.
Identify implications for gatekeeper obligations, interoperability mandates, data access \
requirements, self-preferencing prohibitions, fine exposure, behavioral and structural \
remedies, merger notification thresholds, and DOJ/FTC enforcement signals.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "affected_gatekeepers":                  [<string>],
  "interoperability_mandates":             [<string>],
  "data_access_obligations":               [<string>],
  "self_preferencing_prohibitions":        [<string>],
  "fine_exposure_pct_global_revenue":      <float — maximum fine as % of global revenue; 0.0 if unknown>,
  "behavioral_remedy_changes":             [<string>],
  "structural_remedy_risk":                <bool>,
  "merger_notification_threshold_changes": [<string>],
  "doj_ftc_enforcement_signal":            "increase" | "decrease" | "neutral" | "unknown",
  "action_items":                          [<string>],
  "confidence":                            <float 0-1>,
  "summary":                               "<concise platform antitrust impact summary>"
}
"""

_USER_TEMPLATE = """\
FILING ID:      {filing_id}
DOMAIN:         {domain}
TITLE:          {title}
PUBLISHED DATE: {published_date}
SOURCE URL:     {source_url}
BUSINESS LINES: {business_lines}

FILING TEXT:
{raw_text}
{memory_block}\
"""


class PlatformAntitrustSkill(Skill):
    metadata = SkillMetadata(
        name="platform_antitrust_impact",
        description=(
            "Analyse regulatory filings for digital platform competition law implications "
            "— maps DMA/DSA gatekeeper obligations, FTC/DOJ enforcement signals, "
            "interoperability mandates, and structural remedy risks. Designed for platform "
            "operators, Big Tech regulatory affairs teams, and M&A counsel."
        ),
        version="1.0.0",
        permissions=Permission.LLM_READ | Permission.LLM_WRITE | Permission.MEMORY_READ,
        latency=LatencyClass.MODERATE,
        parameters=[
            SkillParameter(
                "filing",
                "dict",
                "Serialized RegulatoryFiling with id, title, domain, raw_text, etc.",
            ),
            SkillParameter(
                "memory_context",
                "str",
                "Pre-built memory context block to append to the prompt.",
                required=False,
                default="",
            ),
        ],
        returns=(
            "dict — {affected_gatekeepers, interoperability_mandates, data_access_obligations, "
            "self_preferencing_prohibitions, fine_exposure_pct_global_revenue, "
            "behavioral_remedy_changes, structural_remedy_risk, "
            "merger_notification_threshold_changes, doj_ftc_enforcement_signal, "
            "action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "platform",
            "antitrust",
            "dma",
            "dsa",
            "ftc",
            "competition",
            "gatekeeper",
        ],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        if context.llm is None:
            return SkillResult(
                skill_name=self.metadata.name,
                success=False,
                data=None,
                error="LLM access denied — this skill requires LLM_READ permission",
            )

        filing = context.params["filing"]
        memory_context = context.params.get("memory_context", "")
        domain = filing.get("domain", "")
        domain_lines = DOMAIN_BUSINESS_LINES.get(domain, [])

        memory_block = ("\n" + memory_context) if memory_context else ""

        user_prompt = _USER_TEMPLATE.format(
            filing_id=filing.get("id", "UNKNOWN"),
            domain=domain.upper(),
            title=filing.get("title", ""),
            published_date=filing.get("published_date", ""),
            source_url=filing.get("source_url", ""),
            raw_text=filing.get("raw_text", ""),
            business_lines=", ".join(domain_lines),
            memory_block=memory_block,
        )

        raw = context.llm.complete(
            PLATFORM_ANTITRUST_SYSTEM, user_prompt, temperature=0.1
        )

        fallback = {
            "affected_gatekeepers": [],
            "interoperability_mandates": [],
            "data_access_obligations": [],
            "self_preferencing_prohibitions": [],
            "fine_exposure_pct_global_revenue": 0.0,
            "behavioral_remedy_changes": [],
            "structural_remedy_risk": False,
            "merger_notification_threshold_changes": [],
            "doj_ftc_enforcement_signal": "unknown",
            "action_items": [],
            "confidence": 0.3,
            "summary": raw[:500],
        }
        parsed = parse_llm_json(raw, fallback=fallback)

        parsed["filing_id"] = filing.get("id", "UNKNOWN")
        parsed["domain"] = domain

        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data=parsed,
            token_usage=len(user_prompt) // 4 + len(raw) // 4,
            metadata={
                "filing_id": filing.get("id"),
                "doj_ftc_enforcement_signal": parsed.get("doj_ftc_enforcement_signal"),
            },
        )
