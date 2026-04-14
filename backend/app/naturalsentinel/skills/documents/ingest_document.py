"""Skill: Ingest a document through the Document Intelligence pipeline."""

from app.naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)


class IngestDocumentSkill(Skill):
    metadata = SkillMetadata(
        name="ingest_document",
        description=(
            "Ingest a document (PDF, DOCX, HTML, Markdown, text) through the "
            "Document Intelligence pipeline. Parses the document into its structural "
            "hierarchy, generates L0/L1/L2 tiers, indexes embeddings in Qdrant, and "
            "writes the hierarchy to OpenViking. Accepts a URL, absolute file path, "
            "or base64-encoded content. Returns doc_id, viking:// URI, section count, "
            "and L0 structure summary."
        ),
        version="1.0.0",
        permissions=(
            Permission.FETCH_NETWORK
            | Permission.FILE_READ
            | Permission.FILE_WRITE
            | Permission.MEMORY_WRITE
        ),
        latency=LatencyClass.SLOW,
        parameters=[
            SkillParameter(
                "source_url",
                "str",
                "URL to fetch document from.",
                required=False,
                default="",
            ),
            SkillParameter(
                "file_path",
                "str",
                "Absolute local file path (CLI use only).",
                required=False,
                default="",
            ),
            SkillParameter(
                "content_b64",
                "str",
                "Base64-encoded file content.",
                required=False,
                default="",
            ),
            SkillParameter(
                "content_type", "str", "MIME type hint.", required=False, default=""
            ),
            SkillParameter(
                "doc_type",
                "str",
                "Document type: 'legal', 'medical', 'compliance', 'generic', or 'auto'.",
                required=False,
                default="auto",
            ),
            SkillParameter(
                "metadata",
                "dict",
                "Extra metadata (tags, client_name, etc.).",
                required=False,
                default={},
            ),
        ],
        returns="dict — doc_id, uri, title, doc_type, section_count, status, structure_summary",
        dependencies=[],
        max_token_budget=0,
        cacheable=False,
        tags=["document", "ingest", "indexing"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        from app.naturalsentinel.documents.pipeline import ingest_document

        source_url = context.params.get("source_url", "")
        file_path = context.params.get("file_path", "")
        content_b64 = context.params.get("content_b64", "")
        content_type = context.params.get("content_type", "")
        doc_type = context.params.get("doc_type", "auto")
        metadata = context.params.get("metadata", {})

        if not any([source_url, file_path, content_b64]):
            return SkillResult(
                success=False,
                error="Provide one of: source_url, file_path, content_b64",
            )

        # Resolve clients from context extras if available
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

        result = ingest_document(
            source_url=source_url,
            file_path=file_path,
            content_b64=content_b64,
            content_type=content_type,
            doc_type=doc_type,
            metadata=metadata,
            ov_client=ov_client,
            qdrant_client=qdrant_client,
        )
        return SkillResult(success=True, data=result)
