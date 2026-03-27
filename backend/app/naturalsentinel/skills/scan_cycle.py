"""Skill: Full regulatory scan cycle — composes fetch, dedup, analyze, store."""

from app.naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)


class ScanCycleSkill(Skill):
    metadata = SkillMetadata(
        name="scan_cycle",
        description=(
            "Execute a complete regulatory monitoring cycle: fetch filings → "
            "deduplicate → build memory context → analyze each with LLM → "
            "store results. This is the primary entrypoint that composes "
            "lower-level skills into a coherent workflow."
        ),
        version="1.0.0",
        permissions=(
            Permission.FETCH_LOCAL
            | Permission.LLM_READ
            | Permission.LLM_WRITE
            | Permission.MEMORY_READ
            | Permission.MEMORY_WRITE
            | Permission.STATE_READ
            | Permission.STATE_WRITE
        ),
        latency=LatencyClass.BATCH,
        parameters=[
            SkillParameter(
                "domains",
                "list[str]",
                "Agency codes to scan.",
                required=False,
                default=[],
            ),
            SkillParameter(
                "since_days", "int", "Look-back window.", required=False, default=30
            ),
        ],
        returns="dict — {results: list[dict], stats: dict}",
        dependencies=[
            "fetch_filings",
            "detect_duplicates",
            "build_context",
            "analyze_filing",
            "store_memory",
        ],
        max_token_budget=50000,
        tags=["orchestration", "core", "batch"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        domains = context.params.get("domains", [])
        since_days = context.params.get("since_days", 30)

        # Step 1: Fetch
        fetch_result = context.invoke_skill(
            "fetch_filings",
            {
                "domains": domains,
                "since_days": since_days,
            },
        )
        if not fetch_result.success:
            return SkillResult(
                skill_name=self.metadata.name,
                success=False,
                data=None,
                error=f"Fetch failed: {fetch_result.error}",
            )

        all_filings = fetch_result.data

        # Step 2: Deduplicate
        dedup_result = context.invoke_skill(
            "detect_duplicates",
            {
                "filings": all_filings,
                "mark_seen": True,
            },
        )
        if not dedup_result.success:
            return SkillResult(
                skill_name=self.metadata.name,
                success=False,
                data=None,
                error=f"Dedup failed: {dedup_result.error}",
            )

        new_filings = dedup_result.data["new_filings"]
        if not new_filings:
            return SkillResult(
                skill_name=self.metadata.name,
                success=True,
                data={
                    "results": [],
                    "stats": {"total": len(all_filings), "new": 0, "analyzed": 0},
                },
                metadata={"message": "No new filings to analyze"},
            )

        # Step 3-5: For each filing → build context → analyze → store
        results = []
        total_tokens = 0

        for filing in new_filings:
            # 3. Build memory context
            ctx_result = context.invoke_skill(
                "build_context",
                {
                    "domain": filing.get("domain", ""),
                    "filing_text": filing.get("raw_text", ""),
                },
            )
            mem_context = ctx_result.data if ctx_result.success else ""

            # 4. Analyze
            analyze_result = context.invoke_skill(
                "analyze_filing",
                {
                    "filing": filing,
                    "memory_context": mem_context,
                },
            )
            if not analyze_result.success:
                results.append(
                    {"filing_id": filing.get("id"), "error": analyze_result.error}
                )
                continue

            impact = analyze_result.data
            total_tokens += analyze_result.token_usage

            # 5. Store in memory
            context.invoke_skill(
                "store_memory",
                {
                    "filing_id": filing.get("id", "UNKNOWN"),
                    "filing": filing,
                    "impact": impact,
                },
            )

            results.append(
                {
                    "filing": filing,
                    "impact": impact,
                }
            )

        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data={
                "results": results,
                "stats": {
                    "total_fetched": len(all_filings),
                    "duplicates_skipped": dedup_result.data["duplicates_skipped"],
                    "new_analyzed": len(results),
                    "errors": sum(1 for r in results if "error" in r),
                },
            },
            token_usage=total_tokens,
            metadata={"domains": domains or "all"},
        )
