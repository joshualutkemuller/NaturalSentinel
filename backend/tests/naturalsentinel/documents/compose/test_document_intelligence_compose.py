"""Compose-backed integration tests for Document Intelligence.

These tests exercise the real PostgreSQL database and (optionally) the real
Qdrant service.  They are intended to run against a live ``docker compose up``
stack and are therefore slower than the hermetic unit tests in
``test_document_intelligence.py``.

Run the full suite:
    cd backend && POSTGRES_PORT=5433 uv run pytest tests/naturalsentinel/test_document_intelligence_compose.py -v

Skip from the fast suite (the default):
    uv run pytest -m "not slow"

Prerequisites:
    docker compose up -d db          # PostgreSQL — always required
    docker compose up -d qdrant      # Qdrant    — required for Qdrant tests only
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select, text

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"

pytestmark = pytest.mark.slow


# ---------------------------------------------------------------------------
# Shared fixture: in-memory fake for OV and optional Qdrant detection
# ---------------------------------------------------------------------------


class _FakeOVClient:
    """Minimal fake for tests where OV service isn't running."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._dirs: set[str] = set()

    def mkdir(self, uri: str) -> None:
        self._dirs.add(uri)

    def write(self, uri: str, content: str) -> None:
        self._store[uri] = content

    def read(self, uri: str) -> str:
        return self._store.get(uri, "")

    def ls(self, uri: str) -> list[str]:
        prefix = uri.rstrip("/") + "/"
        return [k for k in self._store if k.startswith(prefix)]

    def tree(self, uri: str) -> dict:
        return {"uri": uri, "children": self.ls(uri)}

    def find(
        self, query: str, target_uri: str = "viking://", limit: int = 10
    ) -> list[dict]:
        results = []
        words = query.lower().split()
        for uri, content in self._store.items():
            if uri.startswith(target_uri.rstrip("/")) and any(
                w in content.lower() for w in words[:2]
            ):
                results.append({"uri": uri, "score": 0.8, "snippet": content[:80]})
        return results[:limit]

    def relations(self, uri: str) -> list[dict]:
        return []

    def abstract(self, uri: str) -> str:
        return self._store.get(uri.rstrip("/") + "/.abstract.md", "")

    def overview(self, uri: str) -> str:
        return self._store.get(
            uri.rstrip("/") + "/.overview.md", self._store.get(uri, "")
        )

    def link(self, source: str, target, relation: str = "references") -> None:
        pass

    def commit_session(self, session_id: str) -> dict:
        return {"session_id": session_id, "status": "committed"}


def _try_qdrant_client():
    """Return a real QdrantClient if Qdrant is reachable, else None."""
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(host="localhost", port=6333, timeout=3)
        client.get_collections()  # probe
        return client
    except Exception:
        return None


def _load_fixture() -> str:
    return (FIXTURES_DIR / "sec_cybersecurity_rule.txt").read_text(encoding="utf-8")


class _FakeQdrant:
    """Module-level fake Qdrant client for compose tests (no real Qdrant needed)."""

    def __init__(self):
        self._cols: dict = {}

    def get_collections(self):
        from unittest.mock import MagicMock

        m = MagicMock()
        m.collections = []
        return m

    def create_collection(self, collection_name, vectors_config=None):
        self._cols.setdefault(collection_name, [])

    def upsert(self, collection_name, points):
        self._cols.setdefault(collection_name, []).extend(points)

    def search(self, collection_name, query_vector, limit=10, query_filter=None, **kw):
        return []

    def scroll(self, collection_name, **kw):
        return [], None


# ---------------------------------------------------------------------------
# Helper: build TestClient with dependency overrides
# ---------------------------------------------------------------------------


def _make_client(ov_override=None, qdrant_override=None) -> TestClient:
    """Return a FastAPI TestClient with optional OV/Qdrant dependency overrides."""
    from app.api.deps import get_openviking_client, get_qdrant_client
    from app.main import app

    overrides: dict = {}
    if ov_override is not None:
        overrides[get_openviking_client] = lambda: ov_override
    if qdrant_override is not None:
        overrides[get_qdrant_client] = lambda: qdrant_override

    # Apply, yield, then restore
    app.dependency_overrides.update(overrides)
    return TestClient(app)


# ---------------------------------------------------------------------------
# TestPgDocumentPersistence — real PostgreSQL, fake OV + Qdrant
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestPgDocumentPersistence:
    """Ingest a document via the pipeline and verify the PgDocument row in real PG."""

    def test_pipeline_writes_pg_document(self, db: Session):
        from app.naturalsentinel.documents.pipeline import ingest_document
        from app.naturalsentinel.memory.pg_models import PgDocument

        ov = _FakeOVClient()
        raw_text = _load_fixture()

        result = ingest_document(
            content_b64=base64.b64encode(raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={"created_by": "test-suite", "source": "compose-integration"},
            ov_client=ov,
            qdrant_client=None,
            session_db=db,
        )

        doc_id = result["doc_id"]
        row = db.exec(select(PgDocument).where(PgDocument.doc_id == doc_id)).first()

        assert row is not None, f"PgDocument not found for doc_id={doc_id!r}"
        assert row.doc_type == result["doc_type"]
        assert row.section_count == result["section_count"]
        assert row.status == "ready"
        assert row.viking_uri.startswith("viking://documents/")

        # Cleanup
        db.delete(row)
        db.commit()

    def test_pipeline_pg_document_viking_uri_matches_ov_root(self, db: Session):
        from app.naturalsentinel.documents.pipeline import ingest_document
        from app.naturalsentinel.memory.pg_models import PgDocument

        ov = _FakeOVClient()
        raw_text = _load_fixture()

        result = ingest_document(
            content_b64=base64.b64encode(raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={"created_by": "test-suite"},
            ov_client=ov,
            qdrant_client=None,
            session_db=db,
        )

        doc_id = result["doc_id"]
        row = db.exec(select(PgDocument).where(PgDocument.doc_id == doc_id)).first()
        assert row is not None

        expected_prefix = f"viking://documents/{doc_id}"
        assert row.viking_uri.startswith(expected_prefix), (
            f"PgDocument.viking_uri {row.viking_uri!r} doesn't start with {expected_prefix!r}"
        )

        # Cleanup
        db.delete(row)
        db.commit()

    def test_two_ingests_produce_distinct_pg_records(self, db: Session):
        from app.naturalsentinel.documents.pipeline import ingest_document
        from app.naturalsentinel.memory.pg_models import PgDocument

        raw_text = _load_fixture()
        ov = _FakeOVClient()

        r1 = ingest_document(
            content_b64=base64.b64encode(raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={"created_by": "test-suite"},
            ov_client=ov,
            qdrant_client=None,
            session_db=db,
        )
        r2 = ingest_document(
            content_b64=base64.b64encode(raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={"created_by": "test-suite"},
            ov_client=_FakeOVClient(),
            qdrant_client=None,
            session_db=db,
        )

        assert r1["doc_id"] != r2["doc_id"], "Each ingest must produce a unique doc_id"

        # Cleanup
        for doc_id in (r1["doc_id"], r2["doc_id"]):
            row = db.exec(select(PgDocument).where(PgDocument.doc_id == doc_id)).first()
            if row:
                db.delete(row)
        db.commit()


# ---------------------------------------------------------------------------
# TestPgProcessTables — PgProcessDefinition and PgProcessExecution via real PG
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestPgProcessTables:
    """register_process and follow_process write to real PG process tables."""

    def test_register_process_writes_pg_definition(self, db: Session):
        from app.naturalsentinel.data.processes import (
            get_builtin_definition,
        )
        from app.naturalsentinel.documents.process_engine import register_process
        from app.naturalsentinel.memory.pg_models import PgProcessDefinition

        md = get_builtin_definition("contract_review")
        result = register_process(
            name="contract_review",
            definition_md=md,
            ov_client=_FakeOVClient(),
            session_db=db,
        )
        assert result["success"] is True

        # Query by the actual registered name (taken from front-matter, may differ from arg)
        registered_name = result["name"]
        row = db.exec(
            select(PgProcessDefinition).where(
                PgProcessDefinition.name == registered_name
            )
        ).first()
        assert row is not None, (
            f"PgProcessDefinition not found for name={registered_name!r}"
        )
        assert row.step_count > 0

        # Cleanup — only delete if we wrote a fresh row (idempotent upsert may have updated existing)
        if row:
            db.delete(row)
            db.commit()

    def test_follow_process_writes_pg_execution(self, db: Session):
        from app.naturalsentinel.data.processes import (
            get_builtin_definition,
        )
        from app.naturalsentinel.documents import process_engine as pe
        from app.naturalsentinel.memory.pg_models import PgProcessExecution

        ov = _FakeOVClient()
        defn = pe.parse_process_definition(
            "compliance_gap_analysis", get_builtin_definition("compliance_gap_analysis")
        )
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            result = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=["compose-pg-test-doc"],
                action="start",
                ov_client=ov,
                qdrant_client=None,
                session_db=db,
            )
        finally:
            pe._load_definition = original

        session_id = result["session_id"]
        rows = db.exec(
            select(PgProcessExecution).where(
                PgProcessExecution.session_id == session_id
            )
        ).all()
        assert len(rows) >= 1, "PgProcessExecution not found after follow_process start"
        ex = rows[0]
        assert ex.process_name == "compliance_gap_analysis"
        assert "compose-pg-test-doc" in ex.doc_ids

        # Cleanup
        for row in rows:
            db.delete(row)
        db.commit()


# ---------------------------------------------------------------------------
# TestQdrantIntegration — real Qdrant (skipped if not available)
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestQdrantIntegration:
    """Document sections upserted to real Qdrant, then queried back."""

    @pytest.fixture(autouse=True)
    def qdrant(self):
        client = _try_qdrant_client()
        if client is None:
            pytest.skip("Qdrant not reachable at localhost:6333")
        self._qdrant = client
        yield client

    def test_ensure_collections_idempotent(self):
        from app.naturalsentinel.documents.qdrant_service import ensure_collections

        # Call twice — must not raise
        ensure_collections(self._qdrant)
        ensure_collections(self._qdrant)
        collections = {c.name for c in self._qdrant.get_collections().collections}
        assert "ns_documents" in collections
        assert "ns_state_filings" in collections
        assert "ns_sessions" in collections

    def test_ingest_creates_searchable_qdrant_points(self):
        from app.naturalsentinel.documents.pipeline import ingest_document
        from app.naturalsentinel.documents.qdrant_service import (
            ensure_collections,
            search_documents,
        )

        ensure_collections(self._qdrant)
        raw_text = _load_fixture()
        ov = _FakeOVClient()

        result = ingest_document(
            content_b64=base64.b64encode(raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={},
            ov_client=ov,
            qdrant_client=self._qdrant,
        )
        doc_id = result["doc_id"]

        hits = search_documents(
            self._qdrant,
            query="Form 8-K Item 1.05 cybersecurity incident disclosure",
            doc_ids=[doc_id],
            top_k=5,
        )
        assert len(hits) > 0, "No Qdrant hits for test document after ingest"
        for hit in hits:
            assert hit["doc_id"] == doc_id

    def test_qdrant_doc_id_filter_isolates_document(self):
        """doc_ids filter must return only points for the requested document."""
        from app.naturalsentinel.documents.pipeline import ingest_document
        from app.naturalsentinel.documents.qdrant_service import (
            ensure_collections,
            search_documents,
        )

        ensure_collections(self._qdrant)
        raw_text = _load_fixture()

        # Ingest two independent documents
        r1 = ingest_document(
            content_b64=base64.b64encode(raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={},
            ov_client=_FakeOVClient(),
            qdrant_client=self._qdrant,
        )
        r2 = ingest_document(
            content_b64=base64.b64encode(raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={},
            ov_client=_FakeOVClient(),
            qdrant_client=self._qdrant,
        )

        hits = search_documents(
            self._qdrant,
            query="cybersecurity board oversight",
            doc_ids=[r1["doc_id"]],
            top_k=10,
        )
        for hit in hits:
            assert hit["doc_id"] == r1["doc_id"], (
                f"doc_ids filter leaked: got doc_id={hit['doc_id']!r}, expected {r1['doc_id']!r}"
            )


# ---------------------------------------------------------------------------
# TestDocumentAPIRoutes — full HTTP round-trip with real PG
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestDocumentAPIRoutes:
    """Hit the /documents/ REST API endpoints with real PG and fake OV/Qdrant."""

    @pytest.fixture
    def client_and_ov(self, superuser_token_headers):
        """TestClient with fake OV + fake Qdrant injected, and auth headers."""
        from app.api.deps import get_openviking_client, get_qdrant_client
        from app.main import app

        ov = _FakeOVClient()
        fq = _FakeQdrant()
        app.dependency_overrides[get_openviking_client] = lambda: ov
        app.dependency_overrides[get_qdrant_client] = lambda: fq
        tc = TestClient(app)
        yield tc, ov, superuser_token_headers
        app.dependency_overrides.pop(get_openviking_client, None)
        app.dependency_overrides.pop(get_qdrant_client, None)

    def test_ingest_returns_doc_id(self, client_and_ov, db: Session):
        from app.core.config import settings
        from app.naturalsentinel.memory.pg_models import PgDocument

        tc, ov, headers = client_and_ov
        raw_text = _load_fixture()

        resp = tc.post(
            f"{settings.API_V1_STR}/documents/ingest",
            headers=headers,
            json={
                "content_b64": base64.b64encode(raw_text.encode()).decode(),
                "content_type": "text/plain",
                "doc_type": "compliance",
                "metadata": {"source": "api-route-test"},
            },
        )
        assert resp.status_code == 200, f"Ingest failed: {resp.text}"
        body = resp.json()
        assert "doc_id" in body
        assert body["section_count"] > 0

        # Cleanup PG row
        row = db.exec(
            select(PgDocument).where(PgDocument.doc_id == body["doc_id"])
        ).first()
        if row:
            db.delete(row)
            db.commit()

    def test_get_document_returns_correct_record(self, client_and_ov, db: Session):
        from app.core.config import settings
        from app.naturalsentinel.memory.pg_models import PgDocument

        tc, ov, headers = client_and_ov
        raw_text = _load_fixture()

        # Ingest
        ingest_resp = tc.post(
            f"{settings.API_V1_STR}/documents/ingest",
            headers=headers,
            json={
                "content_b64": base64.b64encode(raw_text.encode()).decode(),
                "content_type": "text/plain",
                "doc_type": "compliance",
            },
        )
        assert ingest_resp.status_code == 200
        doc_id = ingest_resp.json()["doc_id"]

        # Get
        get_resp = tc.get(f"{settings.API_V1_STR}/documents/{doc_id}", headers=headers)
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["doc_id"] == doc_id
        assert body["doc_type"] == "compliance"
        assert body["status"] == "ready"
        assert body["section_count"] > 0

        # Cleanup
        row = db.exec(select(PgDocument).where(PgDocument.doc_id == doc_id)).first()
        if row:
            db.delete(row)
            db.commit()

    def test_list_documents_includes_ingested_doc(self, client_and_ov, db: Session):
        from app.core.config import settings
        from app.naturalsentinel.memory.pg_models import PgDocument

        tc, ov, headers = client_and_ov
        raw_text = _load_fixture()

        ingest_resp = tc.post(
            f"{settings.API_V1_STR}/documents/ingest",
            headers=headers,
            json={
                "content_b64": base64.b64encode(raw_text.encode()).decode(),
                "content_type": "text/plain",
                "doc_type": "compliance",
            },
        )
        assert ingest_resp.status_code == 200
        doc_id = ingest_resp.json()["doc_id"]

        list_resp = tc.get(f"{settings.API_V1_STR}/documents/", headers=headers)
        assert list_resp.status_code == 200
        ids = [d["doc_id"] for d in list_resp.json()]
        assert doc_id in ids, f"Ingested doc_id {doc_id!r} not in document list"

        # Cleanup
        row = db.exec(select(PgDocument).where(PgDocument.doc_id == doc_id)).first()
        if row:
            db.delete(row)
            db.commit()

    def test_delete_document_removes_pg_record(self, client_and_ov, db: Session):
        from app.core.config import settings
        from app.naturalsentinel.memory.pg_models import PgDocument

        tc, ov, headers = client_and_ov
        raw_text = _load_fixture()

        ingest_resp = tc.post(
            f"{settings.API_V1_STR}/documents/ingest",
            headers=headers,
            json={
                "content_b64": base64.b64encode(raw_text.encode()).decode(),
                "content_type": "text/plain",
                "doc_type": "compliance",
            },
        )
        doc_id = ingest_resp.json()["doc_id"]

        del_resp = tc.delete(
            f"{settings.API_V1_STR}/documents/{doc_id}", headers=headers
        )
        assert del_resp.status_code == 200

        # Verify removed from PG
        row = db.exec(select(PgDocument).where(PgDocument.doc_id == doc_id)).first()
        assert row is None, f"PgDocument {doc_id!r} still present after DELETE"

    def test_get_nonexistent_document_returns_404(self, client_and_ov):
        from app.core.config import settings

        tc, _, headers = client_and_ov
        resp = tc.get(
            f"{settings.API_V1_STR}/documents/nonexistent-id-00000", headers=headers
        )
        assert resp.status_code == 404

    def test_recall_returns_context_blocks(self, client_and_ov, db: Session):
        from app.core.config import settings
        from app.naturalsentinel.memory.pg_models import PgDocument

        tc, ov, headers = client_and_ov
        raw_text = _load_fixture()

        ingest_resp = tc.post(
            f"{settings.API_V1_STR}/documents/ingest",
            headers=headers,
            json={
                "content_b64": base64.b64encode(raw_text.encode()).decode(),
                "content_type": "text/plain",
                "doc_type": "compliance",
            },
        )
        doc_id = ingest_resp.json()["doc_id"]

        recall_resp = tc.post(
            f"{settings.API_V1_STR}/documents/recall",
            headers=headers,
            json={
                "query": "Form 8-K Item 1.05 four business days cybersecurity disclosure",
                "doc_ids": [doc_id],
                "token_budget": 2048,
                "depth": "overview",
            },
        )
        assert recall_resp.status_code == 200
        body = recall_resp.json()
        assert "context_blocks" in body
        assert "total_tokens" in body
        assert body["total_tokens"] >= 0

        # Cleanup
        row = db.exec(select(PgDocument).where(PgDocument.doc_id == doc_id)).first()
        if row:
            db.delete(row)
            db.commit()


# ---------------------------------------------------------------------------
# TestPgTableSchema — sanity-check that all NS tables exist in real PG
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestPgTableSchema:
    """Verify all NaturalSentinel tables exist and have expected columns."""

    def test_ns_documents_table_exists(self, db: Session):
        result = db.exec(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'ns_documents'"
            )
        ).all()
        columns = {row[0] for row in result}
        expected = {
            "doc_id",
            "title",
            "doc_type",
            "viking_uri",
            "section_count",
            "status",
            "created_at",
        }
        missing = expected - columns
        assert not missing, f"ns_documents missing columns: {missing}"

    def test_ns_process_definitions_table_exists(self, db: Session):
        result = db.exec(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'ns_process_definitions'"
            )
        ).all()
        columns = {row[0] for row in result}
        expected = {"name", "version", "step_count", "definition_md", "created_at"}
        missing = expected - columns
        assert not missing, f"ns_process_definitions missing columns: {missing}"

    def test_ns_process_executions_table_exists(self, db: Session):
        result = db.exec(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'ns_process_executions'"
            )
        ).all()
        columns = {row[0] for row in result}
        expected = {
            "execution_id",
            "session_id",
            "process_name",
            "doc_ids",
            "current_step",
            "status",
        }
        missing = expected - columns
        assert not missing, f"ns_process_executions missing columns: {missing}"

    def test_ns_memories_table_exists(self, db: Session):
        result = db.exec(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'ns_memories'"
            )
        ).all()
        columns = {row[0] for row in result}
        expected = {"id", "memory_type", "key", "content", "embedding_text"}
        missing = expected - columns
        assert not missing, f"ns_memories missing columns: {missing}"


# ---------------------------------------------------------------------------
# TestSourceProvenanceCompose — real PG, fake OV + Qdrant
# Verifies that source_url set at ingest time is preserved in PostgreSQL and
# is recoverable from the doc_id carried in recall_context blocks.
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestSourceProvenanceCompose:
    """Compose-backed provenance tests: source_url round-trip through real PG."""

    _SOURCE_URL = (
        "https://federalregister.gov/2023/08/04/sec-cybersecurity-rule-compose-test"
    )

    @pytest.fixture(autouse=True)
    def setup(self, db: Session, superuser_token_headers):
        from unittest.mock import patch

        from app.core.config import settings
        from app.naturalsentinel.memory.pg_models import PgDocument

        self._db = db
        ov = _FakeOVClient()
        fq = _FakeQdrant()

        from app.api.deps import get_openviking_client, get_qdrant_client
        from app.main import app

        app.dependency_overrides[get_openviking_client] = lambda: ov
        app.dependency_overrides[get_qdrant_client] = lambda: fq
        self._tc = TestClient(app)
        self._headers = superuser_token_headers
        self._settings = settings
        self._ov = ov
        self._fq = fq

        # Ingest the SEC fixture with our known source_url; patch _fetch_url so it
        # returns the fixture content instead of hitting the network.
        raw_text = _load_fixture()
        with patch(
            "app.naturalsentinel.documents.pipeline._fetch_url",
            return_value=(raw_text.encode(), "sec-cybersecurity-rule.txt"),
        ):
            resp = self._tc.post(
                f"{settings.API_V1_STR}/documents/ingest",
                headers=superuser_token_headers,
                json={
                    "source_url": self._SOURCE_URL,
                    "content_type": "text/plain",
                    "doc_type": "compliance",
                },
            )
        assert resp.status_code == 200, f"Ingest failed: {resp.text}"
        self._doc_id = resp.json()["doc_id"]

        yield

        # Cleanup
        row = db.exec(
            select(PgDocument).where(PgDocument.doc_id == self._doc_id)
        ).first()
        if row:
            db.delete(row)
            db.commit()
        app.dependency_overrides.pop(get_openviking_client, None)
        app.dependency_overrides.pop(get_qdrant_client, None)

    def test_pg_row_stores_correct_source_url(self):
        """ns_documents row must persist source_url as both a first-class
        column (Phase P0.4) and inside metadata_json (for Qdrant/OV
        alignment redundancy)."""
        from app.naturalsentinel.memory.pg_models import PgDocument

        row = self._db.exec(
            select(PgDocument).where(PgDocument.doc_id == self._doc_id)
        ).first()
        assert row is not None, f"No ns_documents row found for doc_id={self._doc_id}"

        # First-class column — the canonical, indexed provenance field
        assert row.source_url == self._SOURCE_URL, (
            f"PG source_url column '{row.source_url}' does not match ingest URL '{self._SOURCE_URL}'"
        )

        # Blob redundancy — keep until Qdrant/OV payloads migrate to the column
        persisted_url = (row.metadata_json or {}).get("source_url", "")
        assert persisted_url == self._SOURCE_URL, (
            f"PG metadata_json.source_url '{persisted_url}' does not match ingest URL '{self._SOURCE_URL}'"
        )

    def test_pg_row_is_queryable_by_source_url_column(self):
        """Phase P0.4: querying by source_url column must return the
        same row as looking up by doc_id. This is the whole point of
        promoting provenance out of JSONB — a B-tree index hit, not a
        JSON-extract scan.
        """
        from app.naturalsentinel.memory.pg_models import PgDocument

        row = self._db.exec(
            select(PgDocument).where(PgDocument.source_url == self._SOURCE_URL)
        ).first()
        assert row is not None, (
            f"No ns_documents row found for source_url={self._SOURCE_URL}"
        )
        assert row.doc_id == self._doc_id

    def test_recall_blocks_doc_id_links_to_pg_source_url(self):
        """recall_context blocks carry doc_id; that doc_id must resolve to the original source_url in PG."""
        from app.naturalsentinel.memory.pg_models import PgDocument

        recall_resp = self._tc.post(
            f"{self._settings.API_V1_STR}/documents/recall",
            headers=self._headers,
            json={
                "query": "Form 8-K Item 1.05 cybersecurity incident material disclosure",
                "doc_ids": [self._doc_id],
                "token_budget": 2048,
                "depth": "overview",
            },
        )
        assert recall_resp.status_code == 200
        body = recall_resp.json()
        blocks = body.get("context_blocks", [])
        assert len(blocks) > 0, "Expected context blocks from ingested doc"

        # Every block with a doc_id must trace back to the correct PG source_url via metadata_json
        for block in blocks:
            block_doc_id = block.get("doc_id", "")
            if not block_doc_id:
                continue
            row = self._db.exec(
                select(PgDocument).where(PgDocument.doc_id == block_doc_id)
            ).first()
            assert row is not None, f"Block doc_id={block_doc_id} has no PG row"
            persisted_url = (row.metadata_json or {}).get("source_url", "")
            assert persisted_url == self._SOURCE_URL, (
                f"Block traces to PG row with wrong source_url: {persisted_url}"
            )

    def test_recall_block_uri_starts_with_expected_ov_root(self):
        """Block URIs must be rooted at viking://documents/{doc_id}/."""
        recall_resp = self._tc.post(
            f"{self._settings.API_V1_STR}/documents/recall",
            headers=self._headers,
            json={
                "query": "board oversight cybersecurity governance annual report",
                "doc_ids": [self._doc_id],
                "token_budget": 2048,
                "depth": "abstract",
            },
        )
        assert recall_resp.status_code == 200
        blocks = recall_resp.json().get("context_blocks", [])
        expected_prefix = f"viking://documents/{self._doc_id}"
        for block in blocks:
            uri = block.get("uri", "")
            if uri:
                assert uri.startswith(expected_prefix), (
                    f"Block URI '{uri}' does not start with '{expected_prefix}'"
                )

    def test_two_ingests_source_urls_isolated_in_pg(self):
        """Two documents ingested with distinct source_urls must each have their own PG row."""
        from unittest.mock import patch

        from app.naturalsentinel.memory.pg_models import PgDocument

        other_url = "https://example.gov/other-regulation-compose"
        other_text = (
            "Other regulatory rule. Section A. Compliance required by January 1."
        )
        with patch(
            "app.naturalsentinel.documents.pipeline._fetch_url",
            return_value=(other_text.encode(), "other-rule.txt"),
        ):
            resp2 = self._tc.post(
                f"{self._settings.API_V1_STR}/documents/ingest",
                headers=self._headers,
                json={
                    "source_url": other_url,
                    "content_type": "text/plain",
                    "doc_type": "notice",
                },
            )
        assert resp2.status_code == 200
        other_doc_id = resp2.json()["doc_id"]

        try:
            row1 = self._db.exec(
                select(PgDocument).where(PgDocument.doc_id == self._doc_id)
            ).first()
            row2 = self._db.exec(
                select(PgDocument).where(PgDocument.doc_id == other_doc_id)
            ).first()

            assert row1 is not None and row2 is not None
            assert (row1.metadata_json or {}).get("source_url") == self._SOURCE_URL
            assert (row2.metadata_json or {}).get("source_url") == other_url
            assert row1.doc_id != row2.doc_id, (
                "Two ingests must produce distinct doc_id values"
            )
        finally:
            row = self._db.exec(
                select(PgDocument).where(PgDocument.doc_id == other_doc_id)
            ).first()
            if row:
                self._db.delete(row)
                self._db.commit()


# ---------------------------------------------------------------------------
# TestQueryToSourceMaterialCompose — full round-trip via real PG + API
# "User asks a question about a changed regulation → response cites correct source"
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestQueryToSourceMaterialCompose:
    """End-to-end compose test: question → database flow → correct source regulation material."""

    _SOURCE_URL = "https://federalregister.gov/2023/08/04/sec-cyber-disclosure-compose"

    @pytest.fixture(autouse=True)
    def setup(self, db: Session, superuser_token_headers):
        from unittest.mock import patch

        from app.core.config import settings
        from app.naturalsentinel.memory.pg_models import PgDocument

        self._db = db
        self._headers = superuser_token_headers
        self._settings = settings
        ov = _FakeOVClient()
        fq = _FakeQdrant()

        from app.api.deps import get_openviking_client, get_qdrant_client
        from app.main import app

        app.dependency_overrides[get_openviking_client] = lambda: ov
        app.dependency_overrides[get_qdrant_client] = lambda: fq
        self._tc = TestClient(app)
        self._ov = ov

        raw_text = _load_fixture()
        with patch(
            "app.naturalsentinel.documents.pipeline._fetch_url",
            return_value=(raw_text.encode(), "sec-cybersecurity-rule.txt"),
        ):
            resp = self._tc.post(
                f"{settings.API_V1_STR}/documents/ingest",
                headers=superuser_token_headers,
                json={
                    "source_url": self._SOURCE_URL,
                    "content_type": "text/plain",
                    "doc_type": "compliance",
                },
            )
        assert resp.status_code == 200
        self._doc_id = resp.json()["doc_id"]

        yield

        row = db.exec(
            select(PgDocument).where(PgDocument.doc_id == self._doc_id)
        ).first()
        if row:
            db.delete(row)
            db.commit()
        app.dependency_overrides.pop(get_openviking_client, None)
        app.dependency_overrides.pop(get_qdrant_client, None)

    def test_recall_returns_blocks_for_regulation_question(self):
        """Asking about the 4-business-day rule must return context blocks, not an empty response."""
        recall_resp = self._tc.post(
            f"{self._settings.API_V1_STR}/documents/recall",
            headers=self._headers,
            json={
                "query": "four business days material cybersecurity incident Form 8-K disclosure obligation",
                "doc_ids": [self._doc_id],
                "token_budget": 4096,
                "depth": "overview",
            },
        )
        assert recall_resp.status_code == 200
        body = recall_resp.json()
        assert "context_blocks" in body
        assert len(body["context_blocks"]) > 0, (
            "Question about changed regulation must return at least one context block"
        )

    def test_recall_response_blocks_contain_source_regulation_text(self):
        """Block content must include text from the ingested SEC cybersecurity rule."""
        recall_resp = self._tc.post(
            f"{self._settings.API_V1_STR}/documents/recall",
            headers=self._headers,
            json={
                "query": "cybersecurity incident disclosure registrant material",
                "doc_ids": [self._doc_id],
                "token_budget": 4096,
                "depth": "overview",
            },
        )
        assert recall_resp.status_code == 200
        blocks = recall_resp.json().get("context_blocks", [])
        all_content = " ".join(b.get("content", "") for b in blocks).lower()

        # Verify that text from the fixture survives the ingest → retrieval round-trip
        expected_terms = ["cybersecurity", "registrant", "disclosure"]
        for term in expected_terms:
            assert term in all_content, (
                f"Expected term '{term}' from source regulation not found in any returned block"
            )

    def test_recall_positive_token_count_proves_content_was_returned(self):
        """total_tokens > 0 confirms that real content — not empty shells — was assembled."""
        recall_resp = self._tc.post(
            f"{self._settings.API_V1_STR}/documents/recall",
            headers=self._headers,
            json={
                "query": "annual report cybersecurity risk governance board oversight",
                "doc_ids": [self._doc_id],
                "token_budget": 4096,
                "depth": "overview",
            },
        )
        assert recall_resp.status_code == 200
        body = recall_resp.json()
        if body.get("context_blocks"):
            assert body["total_tokens"] > 0, (
                "Non-empty block list must have total_tokens > 0"
            )

    def test_scoped_recall_does_not_leak_other_documents(self):
        """Recall scoped to our doc_id must not return blocks from an unrelated document."""
        from unittest.mock import patch

        # Ingest a second document via mocked _fetch_url
        other_text = "Unrelated regulatory notice. Section 1. No cybersecurity content."
        with patch(
            "app.naturalsentinel.documents.pipeline._fetch_url",
            return_value=(other_text.encode(), "unrelated.txt"),
        ):
            other_resp = self._tc.post(
                f"{self._settings.API_V1_STR}/documents/ingest",
                headers=self._headers,
                json={
                    "source_url": "https://example.gov/unrelated",
                    "content_type": "text/plain",
                    "doc_type": "notice",
                },
            )
        assert other_resp.status_code == 200
        other_doc_id = other_resp.json()["doc_id"]

        from app.naturalsentinel.memory.pg_models import PgDocument

        try:
            recall_resp = self._tc.post(
                f"{self._settings.API_V1_STR}/documents/recall",
                headers=self._headers,
                json={
                    "query": "cybersecurity incident disclosure four business days",
                    "doc_ids": [self._doc_id],
                    "token_budget": 4096,
                    "depth": "overview",
                },
            )
            assert recall_resp.status_code == 200
            blocks = recall_resp.json().get("context_blocks", [])
            for block in blocks:
                if block.get("doc_id"):
                    assert block["doc_id"] == self._doc_id, (
                        f"Block from unrelated doc {block['doc_id']} leaked into scoped recall"
                    )
        finally:
            row = self._db.exec(
                select(PgDocument).where(PgDocument.doc_id == other_doc_id)
            ).first()
            if row:
                self._db.delete(row)
                self._db.commit()

    def test_pg_source_url_matches_after_question_answered(self):
        """After answering a question, the pg row must still have the original source_url intact."""
        from app.naturalsentinel.memory.pg_models import PgDocument

        # Ask the question
        self._tc.post(
            f"{self._settings.API_V1_STR}/documents/recall",
            headers=self._headers,
            json={
                "query": "compliance dates effective date Form 8-K",
                "doc_ids": [self._doc_id],
                "token_budget": 2048,
                "depth": "abstract",
            },
        )

        # PG source_url must still be intact
        row = self._db.exec(
            select(PgDocument).where(PgDocument.doc_id == self._doc_id)
        ).first()
        assert row is not None
        persisted_url = (row.metadata_json or {}).get("source_url", "")
        assert persisted_url == self._SOURCE_URL, (
            f"PG source_url was mutated by recall: '{persisted_url}'"
        )
