"""Built-in document review process definitions.

These process definitions ship with NaturalSentinel and are registered
automatically on first call to ``load_builtin_processes()``.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_BUILTIN_DIR = Path(__file__).parent

BUILTIN_PROCESS_NAMES: list[str] = [
    "contract_review",
    "medical_records_review",
    "compliance_gap_analysis",
]


def load_builtin_processes(
    *,
    ov_client=None,
    session_db=None,
    skip_existing: bool = True,
) -> dict[str, dict]:
    """Parse and register all built-in process definitions.

    Args:
        ov_client: OpenViking client for writing process definitions.
        session_db: SQLModel Session for PostgreSQL persistence.
        skip_existing: If True, skip processes that are already registered in the DB.

    Returns:
        Dict mapping process name → registration result dict.
    """
    from app.naturalsentinel.documents.process_engine import register_process

    results: dict[str, dict] = {}

    for name in BUILTIN_PROCESS_NAMES:
        md_path = _BUILTIN_DIR / f"{name}.md"
        if not md_path.exists():
            logger.warning("Built-in process file not found: %s", md_path)
            results[name] = {"success": False, "error": "File not found"}
            continue

        # Check if already registered
        if skip_existing and session_db is not None:
            try:
                from sqlmodel import select

                from app.naturalsentinel.memory.pg_models import PgProcessDefinition

                existing = session_db.exec(
                    select(PgProcessDefinition).where(PgProcessDefinition.name == name)
                ).first()
                if existing:
                    results[name] = {"success": True, "skipped": True, "name": name}
                    continue
            except Exception:
                pass

        definition_md = md_path.read_text(encoding="utf-8")
        result = register_process(
            name=name,
            definition_md=definition_md,
            ov_client=ov_client,
            session_db=session_db,
        )
        results[name] = result
        if result.get("success"):
            logger.info(
                "Registered built-in process: %s (%d steps)",
                name,
                result.get("step_count", 0),
            )
        else:
            logger.warning(
                "Failed to register built-in process %s: %s", name, result.get("error")
            )

    return results


def get_builtin_definition(name: str) -> str | None:
    """Return the markdown text for a named built-in process, or None."""
    md_path = _BUILTIN_DIR / f"{name}.md"
    if md_path.exists():
        return md_path.read_text(encoding="utf-8")
    return None
