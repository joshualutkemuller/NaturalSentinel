"""Process Execution Engine (Layer 5).

Manages registered process definitions and drives their step-by-step execution
across one or more documents.

A *process definition* is a markdown file with YAML front matter specifying
metadata (name, version, doc_types, steps) and a body of numbered ``## Step N``
sections with structured fields.

State is persisted to:
- PostgreSQL: ``PgProcessDefinition`` and ``PgProcessExecution`` tables
- OpenViking: ``viking://sessions/{session_id}/progress/{process_name}.json``

Usage::

    from app.naturalsentinel.documents.process_engine import (
        parse_process_definition, follow_process, get_process_status
    )

    # Register a new process
    defn = parse_process_definition(name="contract_review", markdown_text=...)

    # Start or continue execution
    result = follow_process(
        process_name="contract_review",
        doc_ids=["uuid-..."],
        session_id=None,        # None = start new session
        action="start",
        step_result=None,
        ov_client=...,
        qdrant_client=...,
        session_db=...,
    )
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ProcessStep:
    step_number: int
    name: str
    instruction: str
    retrieval_query: str
    target_sections: list[str]
    depth: str  # "abstract" | "overview" | "detail"
    output_schema: dict[str, Any]
    depends_on: list[int]


@dataclass
class ProcessDefinition:
    name: str
    version: str
    description: str
    doc_types: list[str]
    steps: list[ProcessStep]

    def step_count(self) -> int:
        return len(self.steps)

    def get_step(self, number: int) -> ProcessStep | None:
        for s in self.steps:
            if s.step_number == number:
                return s
        return None


@dataclass
class StepRecord:
    step_number: int
    status: str  # "pending" | "pass" | "fail" | "flagged" | "skipped"
    findings: str = ""
    completed_at: str = ""


@dataclass
class ExecutionState:
    execution_id: str
    session_id: str
    process_name: str
    doc_ids: list[str]
    current_step: int
    total_steps: int
    step_records: list[StepRecord] = field(default_factory=list)
    status: str = "in_progress"  # "in_progress" | "completed" | "paused"

    def completed_count(self) -> int:
        return sum(
            1
            for r in self.step_records
            if r.status in ("pass", "fail", "flagged", "skipped")
        )

    def flagged_count(self) -> int:
        return sum(1 for r in self.step_records if r.status == "flagged")

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "session_id": self.session_id,
            "process_name": self.process_name,
            "doc_ids": self.doc_ids,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "status": self.status,
            "step_records": [asdict(r) for r in self.step_records],
        }

    @classmethod
    def from_dict(cls, data: dict) -> ExecutionState:
        step_records = [StepRecord(**r) for r in data.get("step_records", [])]
        return cls(
            execution_id=data["execution_id"],
            session_id=data["session_id"],
            process_name=data["process_name"],
            doc_ids=data["doc_ids"],
            current_step=data["current_step"],
            total_steps=data["total_steps"],
            status=data.get("status", "in_progress"),
            step_records=step_records,
        )


# ---------------------------------------------------------------------------
# Process definition parser
# ---------------------------------------------------------------------------


def parse_process_definition(name: str, markdown_text: str) -> ProcessDefinition:
    """Parse a markdown process definition into a ProcessDefinition.

    Expected format::

        ---
        name: contract_review_checklist
        version: "1.0"
        doc_types: [legal]
        description: Standard M&A contract review
        steps: 28
        ---

        ## Step 1: Parties & Recitals
        - **instruction**: ...
        - **retrieval_query**: ...
        - **depth**: overview
        - **output**:
          - parties: list
        - **depends_on**: []

    Only ``instruction`` and ``retrieval_query`` are required per step.
    """
    # Extract YAML front matter
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", markdown_text, re.DOTALL)
    front_matter: dict[str, Any] = {}
    body = markdown_text

    if fm_match:
        body = markdown_text[fm_match.end() :]
        for line in fm_match.group(1).splitlines():
            kv = line.split(":", 1)
            if len(kv) == 2:
                key = kv[0].strip()
                val = kv[1].strip().strip("\"'")
                if val.startswith("[") and val.endswith("]"):
                    val = [v.strip().strip("\"'") for v in val[1:-1].split(",")]
                front_matter[key] = val

    # Parse step blocks: "## Step N: Name"
    step_blocks = re.split(r"(?m)^## Step\s+(\d+)[:\s]*(.*?)$", body)
    # re.split with groups gives: [pre, stepnum1, stepname1, body1, stepnum2, stepname2, body2, ...]

    steps: list[ProcessStep] = []
    i = 1  # skip pre-block
    while i + 2 < len(step_blocks):
        step_num = int(step_blocks[i])
        step_name = step_blocks[i + 1].strip()
        step_body = step_blocks[i + 2]

        steps.append(_parse_step_body(step_num, step_name, step_body))
        i += 3

    return ProcessDefinition(
        name=front_matter.get("name", name),
        version=str(front_matter.get("version", "1.0")),
        description=front_matter.get("description", ""),
        doc_types=front_matter.get("doc_types", []),
        steps=steps,
    )


def _parse_step_body(step_num: int, step_name: str, body: str) -> ProcessStep:
    """Extract structured fields from a step markdown block."""

    def _extract_field(field_name: str) -> str:
        pattern = rf"\*\*{field_name}\*\*\s*:\s*(.+?)(?=\n\s*-\s*\*\*|\Z)"
        m = re.search(pattern, body, re.DOTALL)
        return m.group(1).strip() if m else ""

    instruction = _extract_field("instruction") or body.strip()[:300]
    retrieval_query = _extract_field("retrieval_query") or step_name
    depth_raw = _extract_field("depth") or "overview"
    depth = depth_raw if depth_raw in ("abstract", "overview", "detail") else "overview"

    # target_sections: parse list value
    ts_raw = _extract_field("target_sections")
    target_sections: list[str] = []
    if ts_raw:
        target_sections = [s.strip().strip("[]\"'") for s in ts_raw.split(",")]

    # depends_on: parse list of ints
    dep_raw = _extract_field("depends_on")
    depends_on: list[int] = []
    if dep_raw:
        for x in re.findall(r"\d+", dep_raw):
            depends_on.append(int(x))

    # output schema: collect bullet points under **output**
    output_schema: dict[str, Any] = {}
    output_match = re.search(
        r"\*\*output\*\*\s*:\s*(.*?)(?=\n\s*-\s*\*\*|\Z)",
        body,
        re.DOTALL | re.IGNORECASE,
    )
    if output_match:
        for line in output_match.group(1).splitlines():
            kv = re.match(r"\s*-\s*(\w+)\s*:\s*(.+)", line)
            if kv:
                output_schema[kv.group(1)] = kv.group(2).strip()

    return ProcessStep(
        step_number=step_num,
        name=step_name,
        instruction=instruction,
        retrieval_query=retrieval_query,
        target_sections=target_sections,
        depth=depth,
        output_schema=output_schema,
        depends_on=depends_on,
    )


# ---------------------------------------------------------------------------
# Process execution
# ---------------------------------------------------------------------------


def follow_process(
    *,
    process_name: str,
    doc_ids: list[str],
    session_id: str | None = None,
    action: str = "start",
    step_result: dict | None = None,
    ov_client=None,
    qdrant_client=None,
    session_db=None,
) -> dict[str, Any]:
    """Execute one step of a process or return current status.

    Args:
        process_name: Registered process name.
        doc_ids: Documents to process.
        session_id: Existing session to resume. None = start new.
        action: One of ``"start"``, ``"next"``, ``"skip"``, ``"status"``,
            ``"complete"``.
        step_result: Dict with ``findings`` and ``status`` for the just-completed step.
        ov_client: OpenViking client for state persistence and retrieval.
        qdrant_client: Qdrant client for retrieval.
        session_db: SQLModel Session for persistence.

    Returns:
        Dict with session_id, process_name, current_step, context, progress.
    """
    # Load process definition
    defn = _load_definition(process_name, session_db)
    if defn is None:
        return {"error": f"Process '{process_name}' not found. Register it first."}

    # Load or create execution state
    if action == "start" or session_id is None:
        state = _new_execution(defn, doc_ids)
        session_id = state.session_id
    else:
        state = _load_state(session_id, ov_client, session_db)
        if state is None:
            return {"error": f"Session '{session_id}' not found."}

    # Record result for current step
    if step_result and action in ("next", "skip"):
        _record_step_result(
            state,
            step_number=state.current_step,
            status=step_result.get("status", "pass"),
            findings=step_result.get("findings", ""),
        )
        if action == "next":
            state.current_step += 1
        elif action == "skip":
            state.current_step += 1

    if action == "complete":
        state.status = "completed"
        _persist_state(state, ov_client, session_db)
        _commit_session_memory(
            state,
            defn,
            ov_client=ov_client,
            qdrant_client=qdrant_client,
            session_db=session_db,
        )
        return _format_complete(state, defn)

    if action == "status":
        return _format_status(state, defn)

    # Get current step
    step = defn.get_step(state.current_step)
    if step is None:
        state.status = "completed"
        _persist_state(state, ov_client, session_db)
        return _format_complete(state, defn)

    # Retrieve context for this step
    step_context = _retrieve_step_context(step, doc_ids, ov_client, qdrant_client)

    # Persist updated state
    _persist_state(state, ov_client, session_db)

    return {
        "session_id": session_id,
        "process_name": process_name,
        "current_step": {
            "step_number": step.step_number,
            "name": step.name,
            "instruction": step.instruction,
            "retrieval_query": step.retrieval_query,
            "context": step_context,
            "depends_on": step.depends_on,
            "output_schema": step.output_schema,
            "depth": step.depth,
        },
        "progress": {
            "total_steps": state.total_steps,
            "completed": state.completed_count(),
            "flagged": state.flagged_count(),
            "remaining": state.total_steps - state.completed_count(),
        },
    }


def _retrieve_step_context(
    step: ProcessStep, doc_ids: list[str], ov_client, qdrant_client
) -> list[dict]:
    """Retrieve relevant context blocks for a process step."""
    from app.naturalsentinel.documents.retrieval import recall_context

    try:
        result = recall_context(
            query=step.retrieval_query,
            ov_client=ov_client,
            qdrant_client=qdrant_client,
            doc_ids=doc_ids,
            token_budget=4096,
            depth=step.depth,
        )
        return result.get("context_blocks", [])
    except Exception as exc:
        logger.warning("Step context retrieval failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


def _new_execution(defn: ProcessDefinition, doc_ids: list[str]) -> ExecutionState:
    return ExecutionState(
        execution_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        process_name=defn.name,
        doc_ids=doc_ids,
        current_step=1,
        total_steps=defn.step_count(),
    )


def _record_step_result(
    state: ExecutionState, step_number: int, status: str, findings: str
) -> None:
    now = datetime.now(UTC).isoformat()
    # Update existing or append
    for r in state.step_records:
        if r.step_number == step_number:
            r.status = status
            r.findings = findings
            r.completed_at = now
            return
    state.step_records.append(
        StepRecord(
            step_number=step_number, status=status, findings=findings, completed_at=now
        )
    )


def _persist_state(state: ExecutionState, ov_client, session_db) -> None:
    state_json = json.dumps(state.to_dict())

    if ov_client is not None:
        try:
            progress_uri = f"viking://sessions/{state.session_id}/progress/{state.process_name}.json"
            ov_client.write(progress_uri, state_json)
        except Exception as exc:
            logger.debug("OV state persist failed: %s", exc)

    if session_db is not None:
        try:
            _persist_pg_execution(session_db, state)
        except Exception as exc:
            logger.debug("PG execution persist failed: %s", exc)


def _load_state(session_id: str, ov_client, session_db) -> ExecutionState | None:
    # Try OpenViking first (most recent)
    if ov_client is not None:
        try:
            # List progress files for this session
            progress_items = ov_client.ls(f"viking://sessions/{session_id}/progress/")
            for item in progress_items or []:
                uri = item if isinstance(item, str) else item.get("uri", "")
                if uri.endswith(".json"):
                    content = ov_client.read(uri)
                    if content:
                        return ExecutionState.from_dict(json.loads(content))
        except Exception:
            pass

    # Try PostgreSQL
    if session_db is not None:
        try:
            return _load_pg_execution(session_db, session_id)
        except Exception:
            pass

    return None


def _load_definition(process_name: str, session_db) -> ProcessDefinition | None:
    if session_db is None:
        return None
    try:
        from sqlmodel import select

        from app.naturalsentinel.memory.pg_models import PgProcessDefinition

        row = session_db.exec(
            select(PgProcessDefinition).where(PgProcessDefinition.name == process_name)
        ).first()
        if row and row.definition_md:
            return parse_process_definition(process_name, row.definition_md)
    except Exception as exc:
        logger.debug("Could not load process definition from DB: %s", exc)
    return None


def _format_status(state: ExecutionState, defn: ProcessDefinition) -> dict:
    return {
        "session_id": state.session_id,
        "process_name": state.process_name,
        "status": state.status,
        "current_step": state.current_step,
        "progress": {
            "total_steps": state.total_steps,
            "completed": state.completed_count(),
            "flagged": state.flagged_count(),
            "remaining": state.total_steps - state.completed_count(),
        },
        "step_records": [asdict(r) for r in state.step_records],
    }


def _format_complete(state: ExecutionState, defn: ProcessDefinition) -> dict:
    return {
        "session_id": state.session_id,
        "process_name": state.process_name,
        "status": "completed",
        "summary": f"Process '{state.process_name}' completed. {state.completed_count()} steps done, {state.flagged_count()} flagged.",
        "step_records": [asdict(r) for r in state.step_records],
    }


def _persist_pg_execution(session, state: ExecutionState) -> None:
    from sqlmodel import select

    from app.naturalsentinel.memory.pg_models import PgProcessExecution

    existing = session.exec(
        select(PgProcessExecution).where(
            PgProcessExecution.execution_id == state.execution_id
        )
    ).first()

    now = datetime.now(UTC)
    if existing:
        existing.current_step = state.current_step
        existing.completed_steps = state.completed_count()
        existing.flagged_steps = state.flagged_count()
        existing.status = state.status
        existing.updated_at = now
        existing.findings_json = {
            str(r.step_number): asdict(r) for r in state.step_records
        }
        if state.status == "completed":
            existing.completed_at = now
        session.add(existing)
    else:
        row = PgProcessExecution(
            execution_id=state.execution_id,
            session_id=state.session_id,
            process_name=state.process_name,
            doc_ids=state.doc_ids,
            current_step=state.current_step,
            total_steps=state.total_steps,
            completed_steps=state.completed_count(),
            flagged_steps=state.flagged_count(),
            status=state.status,
            started_at=now,
            updated_at=now,
            findings_json={str(r.step_number): asdict(r) for r in state.step_records},
        )
        session.add(row)
    session.commit()


def _load_pg_execution(session, session_id: str) -> ExecutionState | None:
    from sqlmodel import select

    from app.naturalsentinel.memory.pg_models import PgProcessExecution

    rows = session.exec(
        select(PgProcessExecution).where(PgProcessExecution.session_id == session_id)
    ).all()
    if not rows:
        return None
    # Take the most recent
    row = sorted(rows, key=lambda r: r.updated_at, reverse=True)[0]
    step_records = [StepRecord(**v) for v in (row.findings_json or {}).values()]
    return ExecutionState(
        execution_id=row.execution_id,
        session_id=session_id,
        process_name=row.process_name,
        doc_ids=row.doc_ids or [],
        current_step=row.current_step,
        total_steps=row.total_steps,
        step_records=step_records,
        status=row.status,
    )


# ---------------------------------------------------------------------------
# Session memory lifecycle — triple-write on process completion
# ---------------------------------------------------------------------------


def _commit_session_memory(
    state: ExecutionState,
    defn: ProcessDefinition,
    *,
    ov_client,
    qdrant_client,
    session_db,
) -> None:
    """Write session findings to OV, PgMemory, and Qdrant ns_sessions.

    Called when a process execution is completed.  All three writes are
    best-effort — failures are logged but never propagated.
    """
    flagged = [r for r in state.step_records if r.status == "flagged"]
    flagged_summary = "; ".join(
        f"Step {r.step_number}: {str(r.findings)[:120]}" for r in flagged[:5]
    )
    summary_text = (
        f"Process '{state.process_name}' completed. "
        f"{state.completed_count()}/{state.total_steps} steps done, "
        f"{state.flagged_count()} flagged. "
        f"Documents: {', '.join(state.doc_ids[:3])}. "
        + (f"Flagged items: {flagged_summary}" if flagged_summary else "")
    )

    # 1. OpenViking — write session summary file (supplemental to step JSON)
    if ov_client is not None:
        try:
            summary_uri = f"viking://sessions/{state.session_id}/summary.md"
            ov_client.write(
                summary_uri, f"# Session {state.session_id}\n\n{summary_text}\n"
            )
        except Exception as exc:
            logger.debug("OV session summary write failed: %s", exc)

    # 2. PgMemory — store as EPISODIC memory row
    if session_db is not None:
        try:
            from app.naturalsentinel.memory.pg_models import PgMemory

            mem_key = f"process:{state.process_name}:{state.session_id}"
            mem = PgMemory(
                memory_type="EPISODIC",
                key=mem_key,
                content={
                    "session_id": state.session_id,
                    "process_name": state.process_name,
                    "doc_ids": state.doc_ids,
                    "step_count": state.total_steps,
                    "completed": state.completed_count(),
                    "flagged": state.flagged_count(),
                    "step_records": [asdict(r) for r in state.step_records],
                },
                embedding_text=summary_text,
            )
            session_db.add(mem)
            session_db.commit()
        except Exception as exc:
            logger.debug("PgMemory session write failed: %s", exc)

    # 3. Qdrant — embed summary into ns_sessions collection
    if qdrant_client is not None:
        try:
            from qdrant_client.models import PointStruct

            from app.naturalsentinel.documents.qdrant_service import (
                embed_text,
                ensure_collections,
            )

            ensure_collections(qdrant_client)
            vector = embed_text(summary_text)
            point = PointStruct(
                id=state.execution_id,
                vector=vector,
                payload={
                    "session_id": state.session_id,
                    "process_name": state.process_name,
                    "doc_ids": state.doc_ids,
                    "completed": state.completed_count(),
                    "flagged": state.flagged_count(),
                    "summary": summary_text[:500],
                    "completed_at": datetime.now(UTC).isoformat(),
                },
            )
            qdrant_client.upsert(collection_name="ns_sessions", points=[point])
        except Exception as exc:
            logger.debug("Qdrant session memory write failed: %s", exc)


# ---------------------------------------------------------------------------
# Process registration helper
# ---------------------------------------------------------------------------


def register_process(
    *,
    name: str,
    definition_md: str,
    doc_types: list[str] | None = None,
    description: str = "",
    ov_client=None,
    session_db=None,
) -> dict[str, Any]:
    """Parse and persist a process definition.

    Returns validation summary dict.
    """
    try:
        defn = parse_process_definition(name, definition_md)
    except Exception as exc:
        return {"success": False, "error": f"Parse failed: {exc}"}

    step_count = defn.step_count()

    # Persist to PostgreSQL
    if session_db is not None:
        try:
            _persist_pg_definition(session_db, defn, definition_md)
        except Exception as exc:
            logger.warning("Could not persist process definition: %s", exc)

    # Write to OpenViking
    if ov_client is not None:
        try:
            proc_uri = f"viking://processes/{name}"
            ov_client.mkdir(proc_uri)
            ov_client.write(f"{proc_uri}/definition.md", definition_md)
            ov_client.write(
                f"{proc_uri}/.abstract.md",
                f"{step_count}-step process: {defn.description}",
            )
        except Exception as exc:
            logger.debug("OV process write failed: %s", exc)

    return {
        "success": True,
        "name": defn.name,
        "version": defn.version,
        "step_count": step_count,
        "doc_types": defn.doc_types,
        "description": defn.description,
    }


def _persist_pg_definition(
    session, defn: ProcessDefinition, definition_md: str
) -> None:
    from sqlmodel import select

    from app.naturalsentinel.memory.pg_models import PgProcessDefinition

    now = datetime.now(UTC)
    existing = session.exec(
        select(PgProcessDefinition).where(PgProcessDefinition.name == defn.name)
    ).first()

    if existing:
        existing.version = defn.version
        existing.description = defn.description
        existing.doc_types = defn.doc_types
        existing.step_count = defn.step_count()
        existing.definition_md = definition_md
        existing.updated_at = now
        session.add(existing)
    else:
        row = PgProcessDefinition(
            name=defn.name,
            version=defn.version,
            description=defn.description,
            doc_types=defn.doc_types,
            step_count=defn.step_count(),
            definition_md=definition_md,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    session.commit()
