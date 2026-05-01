"""Skill: Telecom Infrastructure Security — analyse regulatory filings for telecom network security and infrastructure obligations.

Designed for network security, regulatory affairs, and infrastructure planning teams.
Parses a regulatory filing for structured telecom infrastructure obligations including
supply chain prohibition changes, rip-and-replace program updates, 5G security
framework changes, and universal service fund modifications.
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

TELECOM_INFRASTRUCTURE_SYSTEM = """\
You are a senior telecom infrastructure and national security regulatory expert with \
expertise in FCC Section 54 universal service, Secure and Trusted Communications \
Networks Act (rip-and-replace), Team Telecom CFIUS-equivalent reviews, and NTIA \
broadband programs (BEAD, ReConnect).
Your task is to extract structured telecom infrastructure security obligation data \
from a regulatory filing.
Identify implications for supply chain prohibition changes to the Covered List, \
network architecture security mandates, universal service fund changes, broadband \
buildout obligations, 5G network slicing security requirements, roaming and \
interconnection rule changes, rip-and-replace program scope, foreign ownership \
restriction changes, and 5G security framework updates.
Output JSON only — no prose, no markdown fences.
Schema:
{
  "supply_chain_prohibition_changes":    [<string>],
  "network_architecture_requirements":   [<string>],
  "universal_service_fund_changes":      [<string>],
  "broadband_buildout_obligations":      [<string>],
  "network_slicing_requirements":        [<string>],
  "roaming_interconnection_changes":     [<string>],
  "equipment_rip_and_replace_scope":     "<string>",
  "foreign_ownership_restriction_changes":[<string>],
  "5g_security_framework_changes":       [<string>],
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


class TelecomInfrastructureSkill(Skill):
    metadata = SkillMetadata(
        name="telecom_infrastructure_security",
        description=(
            "Analyse regulatory filings for telecom network security and infrastructure "
            "obligations — maps supply chain prohibition changes (Huawei/ZTE), "
            "rip-and-replace program updates, 5G security framework changes, and "
            "universal service fund modifications. Actionable for network security, "
            "regulatory affairs, and infrastructure planning teams."
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
            "dict — {supply_chain_prohibition_changes, network_architecture_requirements, "
            "universal_service_fund_changes, broadband_buildout_obligations, "
            "network_slicing_requirements, roaming_interconnection_changes, "
            "equipment_rip_and_replace_scope, foreign_ownership_restriction_changes, "
            "5g_security_framework_changes, action_items, confidence, summary}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "telecom",
            "infrastructure",
            "supply-chain",
            "huawei",
            "zte",
            "5g-security",
            "usf",
            "rip-replace",
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
            TELECOM_INFRASTRUCTURE_SYSTEM, user_prompt, temperature=0.1
        )

        fallback = {
            "supply_chain_prohibition_changes": [],
            "network_architecture_requirements": [],
            "universal_service_fund_changes": [],
            "broadband_buildout_obligations": [],
            "network_slicing_requirements": [],
            "roaming_interconnection_changes": [],
            "equipment_rip_and_replace_scope": "",
            "foreign_ownership_restriction_changes": [],
            "5g_security_framework_changes": [],
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
                "supply_chain_prohibition_changes": parsed.get(
                    "supply_chain_prohibition_changes"
                ),
            },
        )
