"""Skill: Fetch regulatory filings from configured sources."""

from naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)
from naturalsentinel.fetchers import fetch_filings
from naturalsentinel.models import RegulatoryDomain


class FetchFilingsSkill(Skill):
    metadata = SkillMetadata(
        name="fetch_filings",
        description=(
            "Retrieve regulatory filings from configured sources (SEC, CFPB, Fed, "
            "FDA, EPA, USTR). Currently reads from curated sample data; production "
            "version would hit real APIs (EDGAR, Federal Register, etc.)."
        ),
        version="1.0.0",
        permissions=Permission.FETCH_LOCAL,  # Read-only, no LLM, no memory
        latency=LatencyClass.FAST,
        parameters=[
            SkillParameter(
                "domains",
                "list[str]",
                "Agency codes to fetch (e.g. ['sec','fda']). Empty = all.",
                required=False,
                default=[],
            ),
            SkillParameter(
                "since_days", "int", "Look-back window in days.", required=False, default=30
            ),
        ],
        returns="list[dict] — serialized RegulatoryFiling objects",
        dependencies=[],
        max_token_budget=0,
        cacheable=True,
        tags=["fetch", "data-source", "regulatory"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        domains_raw = context.params.get("domains", [])
        since_days = context.params.get("since_days", 30)

        domains = [RegulatoryDomain(d) for d in domains_raw] if domains_raw else None
        filings = fetch_filings(domains=domains, since_days=since_days)

        serialized = [
            {
                "id": f.id,
                "title": f.title,
                "domain": f.domain.value,
                "source_url": f.source_url,
                "published_date": f.published_date,
                "change_type": f.change_type.value,
                "raw_text": f.raw_text,
                "fetched_at": f.fetched_at,
            }
            for f in filings
        ]

        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data=serialized,
            metadata={"count": len(serialized), "domains": domains_raw or "all"},
        )
