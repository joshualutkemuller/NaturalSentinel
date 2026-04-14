"""Skill: Tiered context retrieval across indexed documents."""

from app.naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)


class RecallContextSkill(Skill):
    metadata = SkillMetadata(
        name="recall_context",
        description=(
            "Retrieve relevant document context for an agent's query using dual-path "
            "retrieval (Qdrant kNN + OpenViking hierarchical search) fused via "
            "Reciprocal Rank Fusion, assembled within a configurable token budget. "
            "Returns tiered context blocks (L0 abstract / L1 overview / L2 detail) "
            "plus retrieval trajectory metadata."
        ),
        version="1.0.0",
        permissions=Permission.MEMORY_READ | Permission.FETCH_LOCAL,
        latency=LatencyClass.FAST,
        parameters=[
            SkillParameter(
                "query",
                "str",
                "Natural-language question or information need.",
                required=True,
            ),
            SkillParameter(
                "doc_ids",
                "list[str]",
                "Scope to specific documents. Empty = all.",
                required=False,
                default=[],
            ),
            SkillParameter(
                "collections",
                "list[str]",
                "Qdrant collections to search. Default: ['ns_documents'].",
                required=False,
                default=[],
            ),
            SkillParameter(
                "token_budget",
                "int",
                "Max tokens in returned context (default 6144).",
                required=False,
                default=6144,
            ),
            SkillParameter(
                "depth",
                "str",
                "Max retrieval level: 'abstract' (L0), 'overview' (L1), 'detail' (L2).",
                required=False,
                default="overview",
            ),
            SkillParameter(
                "include_cross_references",
                "bool",
                "Follow cross-referenced sections (default true).",
                required=False,
                default=True,
            ),
        ],
        returns="dict — context_blocks, total_tokens, retrieval_trajectory",
        dependencies=[],
        max_token_budget=6144,
        cacheable=True,
        tags=["document", "retrieval", "context"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        from app.naturalsentinel.documents.retrieval import recall_context

        query = context.params.get("query", "")
        if not query:
            return SkillResult(success=False, error="'query' is required")

        ov_client = (
            getattr(context, "extras", {}).get("ov_client")
            if hasattr(context, "extras")
            else None
        )
        qdrant_client = (
            getattr(context, "extras", {}).get("qdrant_client")
            if hasattr(context, "extras")
            else None
        )

        doc_ids = context.params.get("doc_ids") or None
        collections = context.params.get("collections") or None

        result = recall_context(
            query=query,
            ov_client=ov_client,
            qdrant_client=qdrant_client,
            doc_ids=doc_ids,
            collections=collections,
            token_budget=context.params.get("token_budget", 6144),
            depth=context.params.get("depth", "overview"),
            include_cross_references=context.params.get(
                "include_cross_references", True
            ),
        )
        return SkillResult(success=True, data=result)
