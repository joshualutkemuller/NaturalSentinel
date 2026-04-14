"""Documents REST API.

Provides REST endpoints for the Document Intelligence pipeline so that
dashboard UIs, batch operations, and non-MCP integrations can access the
same capabilities exposed by document_server.py over MCP.

Endpoints:
    GET  /documents/                       — list user's ingested documents
    POST /documents/ingest                 — ingest a document
    GET  /documents/{doc_id}               — get document status / structure
    DELETE /documents/{doc_id}             — remove a document record

    POST /documents/recall                 — tiered context retrieval query

    GET  /documents/processes/             — list registered process definitions
    POST /documents/processes/             — register a new process definition
    POST /documents/processes/{name}/execute — start or advance a process execution
    GET  /documents/processes/{name}/executions/{session_id} — get execution status
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, OpenVikingDep, QdrantDep, SessionDep
from app.naturalsentinel.memory.pg_models import (
    PgDocument,
    PgProcessDefinition,
    PgProcessExecution,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Document endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[dict])
def list_documents(
    current_user: CurrentUser,
    session: SessionDep,
    doc_type: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """List documents ingested by the current user."""
    from sqlmodel import select

    stmt = (
        select(PgDocument)
        .where(PgDocument.created_by == str(current_user.id))
        .order_by(PgDocument.created_at.desc())
        .limit(limit)
    )
    if doc_type:
        stmt = stmt.where(PgDocument.doc_type == doc_type)

    docs = session.exec(stmt).all()
    return [
        {
            "doc_id": d.doc_id,
            "title": d.title,
            "doc_type": d.doc_type,
            "file_name": d.file_name,
            "file_size": d.file_size,
            "viking_uri": d.viking_uri,
            "section_count": d.section_count,
            "status": d.status,
            "created_at": d.created_at.isoformat(),
            "metadata": d.metadata_json,
        }
        for d in docs
    ]


@router.post("/ingest", response_model=dict)
def ingest_document(
    body: dict[str, Any],
    current_user: CurrentUser,
    session: SessionDep,
    ov_client: OpenVikingDep,
    qdrant_client: QdrantDep,
) -> dict:
    """Ingest a document through the Document Intelligence pipeline.

    Body fields (one of source_url / file_path / content_b64 required):
      - source_url: URL to fetch the document from
      - file_path: Absolute local path (server-side only)
      - content_b64: Base64-encoded file content
      - content_type: MIME type hint
      - doc_type: "legal" | "medical" | "compliance" | "generic" | "auto"
      - metadata: dict of extra metadata (client_name, matter_id, tags, etc.)
    """
    from app.naturalsentinel.documents.pipeline import ingest_document as _ingest

    source_url = body.get("source_url", "")
    file_path = body.get("file_path", "")
    content_b64 = body.get("content_b64", "")

    if not any([source_url, file_path, content_b64]):
        raise HTTPException(
            status_code=422,
            detail="Provide one of: source_url, file_path, content_b64",
        )

    metadata = body.get("metadata", {})
    metadata["created_by"] = str(current_user.id)

    result = _ingest(
        source_url=source_url,
        file_path=file_path,
        content_b64=content_b64,
        content_type=body.get("content_type", ""),
        doc_type=body.get("doc_type", "auto"),
        metadata=metadata,
        ov_client=ov_client,
        qdrant_client=qdrant_client,
    )

    # Persist metadata to PgDocument
    _upsert_pg_document(session=session, result=result, user_id=str(current_user.id))
    return result


@router.get("/{doc_id}", response_model=dict)
def get_document(
    doc_id: str,
    current_user: CurrentUser,
    session: SessionDep,
    ov_client: OpenVikingDep,
    qdrant_client: QdrantDep,
) -> dict:
    """Get structure summary and metadata for a specific document."""
    from sqlmodel import select

    db_doc = session.exec(
        select(PgDocument).where(
            PgDocument.doc_id == doc_id,
            PgDocument.created_by == str(current_user.id),
        )
    ).first()

    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found")

    status: dict[str, Any] = {
        "doc_id": db_doc.doc_id,
        "title": db_doc.title,
        "doc_type": db_doc.doc_type,
        "file_name": db_doc.file_name,
        "file_size": db_doc.file_size,
        "viking_uri": db_doc.viking_uri,
        "section_count": db_doc.section_count,
        "status": db_doc.status,
        "created_at": db_doc.created_at.isoformat(),
        "metadata": db_doc.metadata_json,
        "structure": db_doc.structure_json,
    }

    # Enrich with live OV section listing
    if ov_client is not None and db_doc.viking_uri:
        try:
            sections = ov_client.ls(db_doc.viking_uri)
            status["sections"] = sections
        except Exception:
            pass

    return status


@router.delete("/{doc_id}", response_model=dict)
def delete_document(
    doc_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Remove a document record. Does not delete the OV/Qdrant data."""
    from sqlmodel import select

    db_doc = session.exec(
        select(PgDocument).where(
            PgDocument.doc_id == doc_id,
            PgDocument.created_by == str(current_user.id),
        )
    ).first()

    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found")

    session.delete(db_doc)
    session.commit()
    return {"message": f"Document {doc_id} deleted"}


# ---------------------------------------------------------------------------
# Recall endpoint
# ---------------------------------------------------------------------------


@router.post("/recall", response_model=dict)
def recall_context(
    body: dict[str, Any],
    current_user: CurrentUser,
    ov_client: OpenVikingDep,
    qdrant_client: QdrantDep,
) -> dict:
    """Tiered context retrieval across indexed documents.

    Body fields:
      - query (required): natural-language question
      - doc_ids: scope to specific documents
      - collections: Qdrant collections (default: ns_documents)
      - token_budget: max tokens (default: 6144)
      - depth: "abstract" | "overview" | "detail" (default: "overview")
      - include_cross_references: bool (default: true)
    """
    from app.naturalsentinel.documents.retrieval import recall_context as _recall

    query = body.get("query", "")
    if not query:
        raise HTTPException(status_code=422, detail="'query' is required")

    return _recall(
        query=query,
        ov_client=ov_client,
        qdrant_client=qdrant_client,
        doc_ids=body.get("doc_ids") or None,
        collections=body.get("collections") or None,
        token_budget=int(body.get("token_budget", 6144)),
        depth=body.get("depth", "overview"),
        include_cross_references=bool(body.get("include_cross_references", True)),
    )


# ---------------------------------------------------------------------------
# Process definition endpoints
# ---------------------------------------------------------------------------


@router.get("/processes/", response_model=list[dict])
def list_processes(
    current_user: CurrentUser,
    session: SessionDep,
) -> list[dict]:
    """List all registered process definitions."""
    from sqlmodel import select

    defs = session.exec(select(PgProcessDefinition)).all()
    return [
        {
            "name": d.name,
            "version": d.version,
            "description": d.description,
            "doc_types": d.doc_types,
            "step_count": d.step_count,
            "viking_uri": d.viking_uri,
            "created_at": d.created_at.isoformat(),
        }
        for d in defs
    ]


@router.post("/processes/", response_model=dict)
def register_process(
    body: dict[str, Any],
    current_user: CurrentUser,
    session: SessionDep,
    ov_client: OpenVikingDep,
) -> dict:
    """Register a new document review process definition.

    Body fields:
      - name (required): unique process identifier
      - definition_md (required): full markdown definition text
      - doc_types: list of applicable document types
      - description: human-readable description
    """
    from app.naturalsentinel.documents.process_engine import register_process as _reg

    name = body.get("name", "")
    definition_md = body.get("definition_md", "")
    if not name or not definition_md:
        raise HTTPException(
            status_code=422, detail="'name' and 'definition_md' are required"
        )

    result = _reg(
        name=name,
        definition_md=definition_md,
        doc_types=body.get("doc_types", []),
        description=body.get("description", ""),
        ov_client=ov_client,
        session_db=session,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/processes/{process_name}/execute", response_model=dict)
def execute_process(
    process_name: str,
    body: dict[str, Any],
    current_user: CurrentUser,
    session: SessionDep,
    ov_client: OpenVikingDep,
    qdrant_client: QdrantDep,
) -> dict:
    """Start or advance a process execution.

    Body fields:
      - doc_ids (required): documents to review
      - session_id: resume existing session (omit to start new)
      - action: "start" | "next" | "skip" | "status" | "complete" (default: start)
      - step_result: findings for the completed step {findings, status}
    """
    from app.naturalsentinel.documents.process_engine import follow_process

    doc_ids = body.get("doc_ids", [])
    if not doc_ids:
        raise HTTPException(status_code=422, detail="'doc_ids' is required")

    result = follow_process(
        process_name=process_name,
        doc_ids=doc_ids,
        session_id=body.get("session_id") or None,
        action=body.get("action", "start"),
        step_result=body.get("step_result") or None,
        ov_client=ov_client,
        qdrant_client=qdrant_client,
        session_db=session,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/processes/{process_name}/executions/{session_id}", response_model=dict)
def get_execution(
    process_name: str,
    session_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Get the current state of a process execution."""
    from sqlmodel import select

    exec_row = session.exec(
        select(PgProcessExecution).where(
            PgProcessExecution.session_id == session_id,
            PgProcessExecution.process_name == process_name,
        )
    ).first()

    if not exec_row:
        raise HTTPException(status_code=404, detail="Execution not found")

    return {
        "execution_id": exec_row.execution_id,
        "session_id": exec_row.session_id,
        "process_name": exec_row.process_name,
        "doc_ids": exec_row.doc_ids,
        "current_step": exec_row.current_step,
        "total_steps": exec_row.total_steps,
        "completed_steps": exec_row.completed_steps,
        "flagged_steps": exec_row.flagged_steps,
        "status": exec_row.status,
        "started_at": exec_row.started_at.isoformat(),
        "updated_at": exec_row.updated_at.isoformat(),
        "completed_at": exec_row.completed_at.isoformat()
        if exec_row.completed_at
        else None,
        "findings": exec_row.findings_json,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _upsert_pg_document(*, session: Any, result: dict, user_id: str) -> None:
    """Write or update a PgDocument record after a successful ingest."""
    from datetime import UTC, datetime

    from sqlmodel import select

    doc_id = result.get("doc_id", "")
    if not doc_id:
        return

    existing = session.exec(
        select(PgDocument).where(PgDocument.doc_id == doc_id)
    ).first()

    now = datetime.now(UTC)

    persisted_meta = dict(result.get("metadata") or {})
    if result.get("source_url"):
        persisted_meta["source_url"] = result["source_url"]

    if existing:
        existing.title = result.get("title", existing.title)
        existing.doc_type = result.get("doc_type", existing.doc_type)
        existing.section_count = result.get("section_count", existing.section_count)
        existing.status = result.get("status", existing.status)
        existing.viking_uri = result.get("uri", existing.viking_uri)
        existing.metadata_json = persisted_meta
        existing.structure_json = result.get("structure_summary", {})
        existing.updated_at = now
        session.add(existing)
    else:
        doc = PgDocument(
            doc_id=doc_id,
            title=result.get("title", ""),
            doc_type=result.get("doc_type", "generic"),
            file_name=result.get("file_name", ""),
            file_size=result.get("file_size", 0),
            viking_uri=result.get("uri", ""),
            section_count=result.get("section_count", 0),
            status=result.get("status", "ready"),
            metadata_json=persisted_meta,
            structure_json=result.get("structure_summary", {}),
            created_at=now,
            updated_at=now,
            created_by=user_id,
        )
        session.add(doc)

    session.commit()
