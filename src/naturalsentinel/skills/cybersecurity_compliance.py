"""Skill: Cybersecurity Compliance — identify cybersecurity compliance obligations from regulatory filings.

Designed for CISOs, security compliance teams, and network operations teams. Parses a
regulatory filing for structured cybersecurity obligations including CISA KEV catalog
implications, FCC telecom cyber rules, SEC incident disclosure mandates, and critical
infrastructure security requirements.
"""

from naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)
from naturalsentinel.fetchers import DOMAIN_BUSINESS_LINES
from naturalsentinel.utils.parsing import parse_llm_json

CYBERSECURITY_COMPLIANCE_SYSTEM = """\
You are a senior cybersecurity regulatory specialist with expertise in CISA directives \
and KEV catalog, FCC cybersecurity rules for telecom providers, SEC Form 8-K \
cybersecurity disclosure rules, NIST CSF, and Executive Order 14028 (Improving the \
Nation's Cybersecurity).
Your task is to extract structured cybersecurity compliance obligation data from a \
regulatory filing.
Identify implications for CISA Known Exploited Vulnerabilities patching obligations, \
incident reporting timelines, SEC disclosure mandates, supply chain security \
requirements, network security mandates, vulnerability disclosure program changes, \
FCC telecom cyber requirements, critical infrastructure designations, and mandatory \
patch timelines.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "kev_catalog_implications":            [<string>],
  "incident_reporting_changes":          [<string>],
  "sec_disclosure_obligations":          [<string>],
  "supply_chain_security_requirements":  [<string>],
  "network_security_mandates":           [<string>],
  "vulnerability_disclosure_changes":    [<string>],
  "fcc_telecom_cyber_requirements":      [<string>],
  "critical_infrastructure_designations":[<string>],
  "patching_timeline_requirements":      [<string>],
  "action_items":                        [<string>],
  "confidence":                          <float 0-1>,
  "summary":                             "<concise summary>"
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


class CybersecurityComplianceSkill(Skill):
    metadata = SkillMetadata(
        name="cybersecurity_compliance",
        description=(
            "Identify cybersecurity compliance obligations from regulatory filings — "
            "maps CISA Known Exploited Vulnerabilities (KEV) catalog implications, FCC "
            "telecom cyber rules, SEC incident disclosure mandates, and critical "
            "infrastructure security requirements. Actionable for CISOs, security "
            "compliance, and network operations teams."
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
            "dict — {kev_catalog_implications, incident_reporting_changes, "
            "sec_disclosure_obligations, supply_chain_security_requirements, "
            "network_security_mandates, vulnerability_disclosure_changes, "
            "fcc_telecom_cyber_requirements, critical_infrastructure_designations, "
            "patching_timeline_requirements, action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "cybersecurity",
            "cisa",
            "kev",
            "fcc",
            "sec-cyber",
            "incident-reporting",
            "critical-infrastructure",
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

        raw = context.llm.complete(CYBERSECURITY_COMPLIANCE_SYSTEM, user_prompt, temperature=0.1)

        fallback = {
            "kev_catalog_implications": [],
            "incident_reporting_changes": [],
            "sec_disclosure_obligations": [],
            "supply_chain_security_requirements": [],
            "network_security_mandates": [],
            "vulnerability_disclosure_changes": [],
            "fcc_telecom_cyber_requirements": [],
            "critical_infrastructure_designations": [],
            "patching_timeline_requirements": [],
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
                "kev_catalog_implications": parsed.get("kev_catalog_implications"),
            },
        )
