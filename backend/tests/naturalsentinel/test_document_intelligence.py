"""Integration tests for the Document Intelligence PRD system.

Uses the real SEC Cybersecurity Disclosure Rule (Release No. 33-11216, August 2023) as the
test document. All storage backends are replaced with lightweight in-memory fakes so the
suite runs offline, without Docker, and without API keys.

Coverage:
  Layer 2  — Structure extraction (legal / compliance extractors)
  Layer 3  — Dual-write to mock Qdrant + mock OpenViking
  Layer 4  — Tiered context retrieval (RRF + token budget assembly)
  Layer 5  — Process definition parser + step-by-step execution
  Layer 6  — Session memory triple-write on process completion
  Block 2  — IndustrySector / StateCode / sector_domains mapping
  sample_data — Real SEC filing entry is present and parses correctly
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# ---------------------------------------------------------------------------
# In-memory fake clients
# ---------------------------------------------------------------------------


class FakeOVClient:
    """Minimal OpenViking SyncHTTPClient fake backed by an in-memory dict."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._dirs: set[str] = set()
        self.mkdir_calls: list[str] = []
        self.write_calls: list[tuple[str, str]] = []
        self.read_calls: list[str] = []

    def mkdir(self, uri: str) -> None:
        self._dirs.add(uri)
        self.mkdir_calls.append(uri)

    def write(self, uri: str, content: str) -> None:
        self._store[uri] = content
        self.write_calls.append((uri, content))

    def read(self, uri: str) -> str:
        self.read_calls.append(uri)
        return self._store.get(uri, "")

    def ls(self, uri: str) -> list[str]:
        prefix = uri.rstrip("/") + "/"
        return [k for k in self._store if k.startswith(prefix)]

    def tree(self, uri: str) -> dict:
        return {"uri": uri, "children": self.ls(uri)}

    def find(
        self, query: str, target: str = "viking://", limit: int = 10
    ) -> list[dict]:
        """Return all stored URIs whose content contains the query words."""
        results = []
        words = query.lower().split()
        for uri, content in self._store.items():
            if uri.startswith(target.rstrip("/")) and all(
                w in content.lower() for w in words[:2]
            ):
                results.append({"uri": uri, "score": 0.9, "snippet": content[:100]})
        return results[:limit]

    def relations(self, uri: str) -> list[dict]:
        return []

    def abstract(self, uri: str) -> str:
        # Pipeline writes to {uri}/.abstract.md — match that exactly
        abstract_uri = uri.rstrip("/") + "/.abstract.md"
        return self._store.get(abstract_uri, "")

    def overview(self, uri: str) -> str:
        # Pipeline writes to {uri}/.overview.md — match that exactly
        overview_uri = uri.rstrip("/") + "/.overview.md"
        return self._store.get(overview_uri, self._store.get(uri, ""))

    def link(self, source: str, target: str, relation: str = "references") -> None:
        pass

    def commit_session(self, session_id: str) -> dict:
        return {"session_id": session_id, "status": "committed"}


@dataclass
class FakeQdrantPoint:
    id: str
    vector: list[float]
    payload: dict = field(default_factory=dict)


class FakeQdrantClient:
    """Minimal Qdrant client fake — supports upsert + scroll + search."""

    def __init__(self):
        self._collections: dict[str, list[FakeQdrantPoint]] = {}
        self.upsert_calls: list[dict] = []

    def get_collections(self):
        mock = MagicMock()
        mock.collections = [MagicMock(name=n) for n in self._collections]
        return mock

    def create_collection(self, collection_name: str, vectors_config=None) -> None:
        self._collections.setdefault(collection_name, [])

    def upsert(self, collection_name: str, points) -> None:
        self._collections.setdefault(collection_name, [])
        self.upsert_calls.append({"collection": collection_name, "count": len(points)})
        existing_ids = {p.id for p in self._collections[collection_name]}
        for pt in points:
            if pt.id not in existing_ids:
                self._collections[collection_name].append(
                    FakeQdrantPoint(id=pt.id, vector=pt.vector, payload=pt.payload)
                )

    def scroll(
        self,
        collection_name: str,
        scroll_filter=None,
        with_payload=True,
        limit=100,
        **kwargs,
    ):
        points = self._collections.get(collection_name, [])
        if scroll_filter:
            must = scroll_filter.get("must", [])
            for condition in must:
                key = condition.get("key", "")
                match_val = condition.get("match", {}).get("value")
                if match_val:
                    points = [p for p in points if p.payload.get(key) == match_val]
        result = []
        for p in points[:limit]:
            mock = MagicMock()
            mock.id = p.id
            mock.payload = p.payload if with_payload else None
            result.append(mock)
        return (result, None)

    def search(
        self, collection_name: str, query_vector, limit=10, query_filter=None, **kwargs
    ):
        """Return top-k points filtered by query_filter (supports MatchValue and MatchAny)."""
        points = self._collections.get(collection_name, [])
        if query_filter:
            must = getattr(query_filter, "must", [])
            for condition in must:
                key = getattr(condition, "key", "")
                match = getattr(condition, "match", None)
                # MatchValue: condition.match.value
                match_val = getattr(match, "value", None)
                # MatchAny: condition.match.any (a list of accepted values)
                match_any = getattr(match, "any", None)
                if key and match_val is not None:
                    points = [p for p in points if p.payload.get(key) == match_val]
                elif key and match_any is not None:
                    accepted = set(match_any)
                    points = [p for p in points if p.payload.get(key) in accepted]
        result = []
        for p in points[:limit]:
            mock = MagicMock()
            mock.id = p.id
            mock.payload = p.payload
            mock.score = 0.85
            result.append(mock)
        return result


class FakeSession:
    """Minimal SQLModel Session fake for process engine persistence."""

    def __init__(self):
        self._rows: list[Any] = []
        self.committed = False

    def add(self, obj) -> None:
        self._rows.append(obj)

    def commit(self) -> None:
        self.committed = True

    def exec(self, stmt):
        """Return empty result set — process engine falls back to OV for state loading."""
        mock = MagicMock()
        mock.first.return_value = None
        mock.all.return_value = []
        return mock

    def delete(self, obj) -> None:
        pass

    def refresh(self, obj) -> None:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_fixture() -> str:
    fixture = FIXTURES_DIR / "sec_cybersecurity_rule.txt"
    return fixture.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------


class TestSampleDataRealFiling(unittest.TestCase):
    """Verify the real SEC Cybersecurity Rule entry is correctly registered."""

    def test_sec_cyb_rule_in_sample_filings(self):
        from app.naturalsentinel.fetchers.sample_data import SAMPLE_FILINGS

        ids = {f["id"] for f in SAMPLE_FILINGS}
        self.assertIn(
            "SEC-2023-0726-CYB",
            ids,
            "Real SEC cybersecurity rule must be in SAMPLE_FILINGS",
        )

    def test_sec_cyb_rule_metadata(self):
        from app.naturalsentinel.fetchers.sample_data import SAMPLE_FILINGS

        entry = next(f for f in SAMPLE_FILINGS if f["id"] == "SEC-2023-0726-CYB")

        self.assertEqual(entry["domain"], "sec")
        self.assertEqual(entry["change_type"], "final_rule")
        self.assertEqual(entry["published_date"], "2023-08-04")
        self.assertIn("cybersecurity", entry["title"].lower())
        self.assertIn("federalregister.gov", entry["source_url"])
        # Raw text references the real CFR section
        self.assertIn("§ 229.106", entry["raw_text"])
        self.assertIn("four business days", entry["raw_text"])

    def test_sec_cyb_rule_in_mock_analyses(self):
        from app.naturalsentinel.fetchers.sample_data import MOCK_ANALYSES

        self.assertIn("SEC-2023-0726-CYB", MOCK_ANALYSES)
        analysis = MOCK_ANALYSES["SEC-2023-0726-CYB"]
        self.assertEqual(analysis["severity"], "high")
        self.assertEqual(analysis["change_type"], "final_rule")
        self.assertIn("2023-12-15", analysis["compliance_deadline"])
        self.assertTrue(len(analysis["action_items"]) >= 5)
        # Must reference Form 8-K
        regs_str = " ".join(analysis["affected_regulations"])
        self.assertIn("8-K", regs_str)

    def test_mock_provider_returns_analysis_for_real_filing(self):
        from app.naturalsentinel.providers.mock import MockProvider

        provider = MockProvider()
        prompt = "FILING ID: SEC-2023-0726-CYB\nTitle: Cybersecurity Disclosure Rule"
        result = provider.complete(system="", user=prompt)
        data = json.loads(result)
        self.assertEqual(data["severity"], "high")
        self.assertIn("Form 8-K", " ".join(data.get("affected_regulations", [])))

    def test_raw_to_filing_normalises_real_entry(self):
        from app.naturalsentinel.fetchers.base import _raw_to_filing
        from app.naturalsentinel.fetchers.sample_data import SAMPLE_FILINGS
        from app.naturalsentinel.models import RegulatoryFiling

        entry = next(f for f in SAMPLE_FILINGS if f["id"] == "SEC-2023-0726-CYB")
        filing = _raw_to_filing(entry)
        self.assertIsInstance(filing, RegulatoryFiling)
        self.assertEqual(filing.id, "SEC-2023-0726-CYB")
        self.assertIsNotNone(filing.domain)


# ---------------------------------------------------------------------------


class TestStructureExtraction(unittest.TestCase):
    """Layer 2 — Document structure extraction from real fixture text."""

    def setUp(self):
        self.raw_text = load_fixture()

    def test_infer_doc_type_compliance(self):
        from app.naturalsentinel.documents.extractors import _infer_doc_type

        doc_type = _infer_doc_type(self.raw_text)
        self.assertIn(
            doc_type,
            ("compliance", "legal"),
            f"Expected compliance or legal, got {doc_type!r}",
        )

    def test_extract_structure_returns_document_tree(self):
        from app.naturalsentinel.documents.extractors import extract_structure
        from app.naturalsentinel.documents.models import DocumentTree

        tree = extract_structure(
            raw_text=self.raw_text,
            doc_id="test-sec-cyb-001",
            doc_type="compliance",
            source_url="https://www.federalregister.gov/documents/2023/08/04/2023-15927/",
            file_name="sec_cybersecurity_rule.txt",
            file_size=len(self.raw_text.encode()),
        )
        self.assertIsInstance(tree, DocumentTree)
        self.assertEqual(tree.doc_id, "test-sec-cyb-001")
        self.assertGreater(len(tree.root_nodes), 0, "Must extract at least one section")

    def test_extracts_article_sections(self):
        from app.naturalsentinel.documents.extractors import extract_structure

        tree = extract_structure(
            raw_text=self.raw_text,
            doc_id="test-sec-cyb-002",
            doc_type="compliance",
            source_url="https://example.gov",
            file_name="sec_cybersecurity_rule.txt",
            file_size=len(self.raw_text.encode()),
        )
        all_titles = [n.title.upper() for n in tree.root_nodes]
        all_titles_joined = " | ".join(all_titles)
        # Fixture has ARTICLE I–V headers; at least one should be captured
        found_articles = any(
            "ARTICLE" in t or "DEFINITIONS" in t or "DISCLOSURE" in t
            for t in all_titles
        )
        self.assertTrue(
            found_articles, f"No article/major sections found in: {all_titles_joined}"
        )

    def test_section_nodes_have_text(self):
        from app.naturalsentinel.documents.extractors import extract_structure

        tree = extract_structure(
            raw_text=self.raw_text,
            doc_id="test-sec-cyb-003",
            doc_type="compliance",
            source_url="https://example.gov",
            file_name="sec_cybersecurity_rule.txt",
            file_size=len(self.raw_text.encode()),
        )
        for node in tree.root_nodes:
            self.assertIsInstance(node.text, str)
            self.assertGreater(len(node.text), 0, f"Node {node.title!r} has empty text")

    def test_section_nodes_have_section_paths(self):
        from app.naturalsentinel.documents.extractors import extract_structure

        tree = extract_structure(
            raw_text=self.raw_text,
            doc_id="test-sec-cyb-004",
            doc_type="compliance",
            source_url="https://example.gov",
            file_name="sec_cybersecurity_rule.txt",
            file_size=len(self.raw_text.encode()),
        )
        for node in tree.root_nodes:
            self.assertIsInstance(node.section_path, str)
            self.assertGreater(
                len(node.section_path), 0, f"Node {node.title!r} has empty section_path"
            )

    def test_char_offsets_are_valid(self):
        from app.naturalsentinel.documents.extractors import extract_structure

        tree = extract_structure(
            raw_text=self.raw_text,
            doc_id="test-sec-cyb-005",
            doc_type="compliance",
            source_url="https://example.gov",
            file_name="sec_cybersecurity_rule.txt",
            file_size=len(self.raw_text.encode()),
        )
        doc_len = len(self.raw_text)
        for node in tree.root_nodes:
            self.assertGreaterEqual(node.char_offset_start, 0)
            self.assertGreaterEqual(node.char_offset_end, node.char_offset_start)
            self.assertLessEqual(node.char_offset_end, doc_len + 1)

    def test_compliance_extractor_detects_cfr_references(self):
        """Compliance extractor annotates CFR/USC citations in metadata."""
        from app.naturalsentinel.documents.extractors import extract_structure

        tree = extract_structure(
            raw_text=self.raw_text,
            doc_id="test-sec-cyb-006",
            doc_type="compliance",
            source_url="https://example.gov",
            file_name="sec_cybersecurity_rule.txt",
            file_size=len(self.raw_text.encode()),
        )
        all_meta = [node.metadata for node in tree.root_nodes]
        # At least one node should have a CFR citation in metadata
        has_cfr = any(
            meta.get("cfr_refs")
            or meta.get("fr_refs")
            or meta.get("obligation_count", 0) > 0
            for meta in all_meta
        )
        self.assertTrue(
            has_cfr,
            "Compliance extractor should detect CFR/obligation references in fixture",
        )


# ---------------------------------------------------------------------------


class TestQdrantDualWrite(unittest.TestCase):
    """Layer 3 — Qdrant dual-write with the fake client."""

    def setUp(self):
        self.raw_text = load_fixture()
        self.qdrant = FakeQdrantClient()

    def test_ensure_collections_creates_ns_documents(self):
        from app.naturalsentinel.documents.qdrant_service import ensure_collections

        ensure_collections(self.qdrant)
        self.assertIn("ns_documents", self.qdrant._collections)
        self.assertIn("ns_state_filings", self.qdrant._collections)
        self.assertIn("ns_sessions", self.qdrant._collections)

    def test_upsert_sections_returns_positive_count(self):
        from app.naturalsentinel.documents.extractors import extract_structure
        from app.naturalsentinel.documents.qdrant_service import (
            ensure_collections,
            upsert_document_sections,
        )

        ensure_collections(self.qdrant)
        tree = extract_structure(
            raw_text=self.raw_text,
            doc_id="test-qdrant-001",
            doc_type="compliance",
            source_url="https://example.gov",
            file_name="sec_cybersecurity_rule.txt",
            file_size=len(self.raw_text.encode()),
        )
        sections = []
        for node in tree.root_nodes:
            sections.append(
                {
                    "chunk_id": node.node_id,
                    "viking_uri": f"viking://documents/test-qdrant-001/{node.uri_path}",
                    "section_path": node.section_path,
                    "node_type": node.node_type,
                    "title": node.title,
                    "text": node.text,
                    "abstract": node.abstract or node.text[:100],
                    "overview": node.overview or node.text[:500],
                    "line_start": node.line_start,
                    "line_end": node.line_end,
                    "char_offset_start": node.char_offset_start,
                    "char_offset_end": node.char_offset_end,
                    "page_number": node.page_number,
                    "word_count": len(node.text.split()),
                }
            )

        count = upsert_document_sections(
            self.qdrant,
            doc_id="test-qdrant-001",
            doc_type="compliance",
            source_url="https://example.gov",
            tags=["cybersecurity", "sec"],
            sections=sections,
        )
        self.assertGreater(
            count, 0, "upsert_document_sections should store at least one point"
        )

    def test_upserted_points_have_doc_id_payload(self):
        from app.naturalsentinel.documents.extractors import extract_structure
        from app.naturalsentinel.documents.qdrant_service import (
            ensure_collections,
            upsert_document_sections,
        )

        ensure_collections(self.qdrant)
        tree = extract_structure(
            raw_text=self.raw_text,
            doc_id="test-qdrant-002",
            doc_type="compliance",
            source_url="https://example.gov",
            file_name="sec_test.txt",
            file_size=len(self.raw_text.encode()),
        )
        sections = [
            {
                "chunk_id": node.node_id,
                "viking_uri": f"viking://documents/test-qdrant-002/{node.uri_path}",
                "section_path": node.section_path,
                "node_type": node.node_type,
                "title": node.title,
                "text": node.text,
                "abstract": node.abstract or node.text[:100],
                "overview": node.overview or node.text[:500],
                "line_start": node.line_start,
                "line_end": node.line_end,
                "char_offset_start": node.char_offset_start,
                "char_offset_end": node.char_offset_end,
                "page_number": node.page_number,
                "word_count": len(node.text.split()),
            }
            for node in tree.root_nodes
        ]
        upsert_document_sections(
            self.qdrant,
            doc_id="test-qdrant-002",
            doc_type="compliance",
            source_url="https://example.gov",
            tags=[],
            sections=sections,
        )
        stored = self.qdrant._collections.get("ns_documents", [])
        self.assertGreater(len(stored), 0)
        for point in stored:
            self.assertEqual(point.payload.get("doc_id"), "test-qdrant-002")
            self.assertIn(point.payload.get("level"), (0, 1, 2))
            self.assertIn("viking_uri", point.payload)

    def test_embed_text_returns_correct_dimension(self):
        from app.naturalsentinel.documents.qdrant_service import embed_text

        vec = embed_text("cybersecurity incident disclosure SEC Form 8-K")
        self.assertEqual(len(vec), 3072)
        self.assertTrue(
            any(v != 0.0 for v in vec),
            "Deterministic mock should return non-zero values",
        )

    def test_embed_text_is_deterministic(self):
        from app.naturalsentinel.documents.qdrant_service import embed_text

        text = "material cybersecurity incident four business days"
        v1 = embed_text(text)
        v2 = embed_text(text)
        self.assertEqual(v1, v2)


# ---------------------------------------------------------------------------


class TestOpenVikingHierarchy(unittest.TestCase):
    """Layer 3 — OpenViking directory structure write with the fake client."""

    def setUp(self):
        self.raw_text = load_fixture()
        self.ov = FakeOVClient()

    def test_pipeline_writes_to_openviking(self):
        from app.naturalsentinel.documents.pipeline import ingest_document

        result = ingest_document(
            source_url="",
            file_path="",
            content_b64=__import__("base64").b64encode(self.raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={"tags": ["cybersecurity", "sec"]},
            ov_client=self.ov,
            qdrant_client=FakeQdrantClient(),
        )
        self.assertIn("doc_id", result)
        # OV should have had mkdir and write calls
        self.assertGreater(
            len(self.ov.mkdir_calls), 0, "Pipeline must create OV directories"
        )
        self.assertGreater(
            len(self.ov.write_calls), 0, "Pipeline must write content to OV"
        )

    def test_pipeline_writes_section_files(self):
        from app.naturalsentinel.documents.pipeline import ingest_document

        result = ingest_document(
            source_url="",
            file_path="",
            content_b64=__import__("base64").b64encode(self.raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={},
            ov_client=self.ov,
            qdrant_client=FakeQdrantClient(),
        )
        doc_id = result["doc_id"]
        base = f"viking://documents/{doc_id}/"
        written_uris = [uri for uri, _ in self.ov.write_calls]
        # At least one URI should be under the doc's namespace
        doc_uris = [u for u in written_uris if base in u]
        self.assertGreater(len(doc_uris), 0, f"No OV files written under {base}")

    def test_ingest_result_has_required_keys(self):
        from app.naturalsentinel.documents.pipeline import ingest_document

        result = ingest_document(
            source_url="",
            file_path="",
            content_b64=__import__("base64").b64encode(self.raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="auto",
            metadata={},
            ov_client=self.ov,
            qdrant_client=FakeQdrantClient(),
        )
        required_keys = {
            "doc_id",
            "uri",
            "title",
            "doc_type",
            "section_count",
            "status",
        }
        self.assertTrue(
            required_keys.issubset(result.keys()),
            f"Missing keys: {required_keys - result.keys()}",
        )
        self.assertGreater(result["section_count"], 0)
        self.assertTrue(result["uri"].startswith("viking://documents/"))


# ---------------------------------------------------------------------------


class TestTieredRetrieval(unittest.TestCase):
    """Layer 4 — Tiered context retrieval with RRF fusion."""

    def setUp(self):
        self.raw_text = load_fixture()
        self.ov = FakeOVClient()
        self.qdrant = FakeQdrantClient()

        # Ingest document into both backends first
        from app.naturalsentinel.documents.pipeline import ingest_document

        result = ingest_document(
            source_url="",
            file_path="",
            content_b64=__import__("base64").b64encode(self.raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={},
            ov_client=self.ov,
            qdrant_client=self.qdrant,
        )
        self.doc_id = result["doc_id"]

    def test_recall_context_returns_dict(self):
        from app.naturalsentinel.documents.retrieval import recall_context

        result = recall_context(
            query="material cybersecurity incident Form 8-K disclosure",
            ov_client=self.ov,
            qdrant_client=self.qdrant,
        )
        self.assertIsInstance(result, dict)
        self.assertIn("context_blocks", result)
        self.assertIn("total_tokens", result)
        self.assertIn("retrieval_trajectory", result)

    def test_recall_context_respects_token_budget(self):
        from app.naturalsentinel.documents.retrieval import recall_context

        result = recall_context(
            query="board oversight cybersecurity governance",
            ov_client=self.ov,
            qdrant_client=self.qdrant,
            token_budget=2048,
        )
        self.assertLessEqual(
            result["total_tokens"],
            2048 + 200,  # small overshoot tolerance for last block
            "total_tokens should respect the configured budget",
        )

    def test_recall_context_doc_id_filter(self):
        from app.naturalsentinel.documents.retrieval import recall_context

        result = recall_context(
            query="cybersecurity incident disclosure",
            ov_client=self.ov,
            qdrant_client=self.qdrant,
            doc_ids=[self.doc_id],
        )
        # All returned blocks should reference our doc_id
        for block in result["context_blocks"]:
            block_doc_id = block.get("doc_id", "")
            if block_doc_id:
                self.assertEqual(block_doc_id, self.doc_id)

    def test_recall_context_abstract_depth(self):
        from app.naturalsentinel.documents.retrieval import recall_context

        result = recall_context(
            query="compliance dates effective date",
            ov_client=self.ov,
            qdrant_client=self.qdrant,
            depth="abstract",
            token_budget=1000,
        )
        # At abstract depth, blocks should not contain full L2 text
        for block in result["context_blocks"]:
            self.assertIn(block.get("level", "L0"), ("L0", "abstract"))

    def test_retrieval_trajectory_populated(self):
        from app.naturalsentinel.documents.retrieval import recall_context

        result = recall_context(
            query="four business days materiality determination",
            ov_client=self.ov,
            qdrant_client=self.qdrant,
        )
        traj = result["retrieval_trajectory"]
        self.assertIsInstance(traj, dict)
        # Trajectory should record the query
        self.assertIn(
            result["retrieval_trajectory"].get("query", ""),
            ["four business days materiality determination", ""],
        )


# ---------------------------------------------------------------------------


class TestProcessEngine(unittest.TestCase):
    """Layer 5 — Process definition parsing and step execution."""

    def setUp(self):
        self.ov = FakeOVClient()
        self.qdrant = FakeQdrantClient()
        self.session = FakeSession()

        # Ingest document so retrieval has data
        raw_text = load_fixture()
        from app.naturalsentinel.documents.pipeline import ingest_document

        result = ingest_document(
            source_url="",
            file_path="",
            content_b64=__import__("base64").b64encode(raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={},
            ov_client=self.ov,
            qdrant_client=self.qdrant,
        )
        self.doc_id = result["doc_id"]

    def _get_compliance_gap_md(self) -> str:
        from app.naturalsentinel.documents.builtin_processes import (
            get_builtin_definition,
        )

        return get_builtin_definition("compliance_gap_analysis")

    def test_parse_builtin_compliance_gap(self):
        from app.naturalsentinel.documents.process_engine import (
            parse_process_definition,
        )

        md = self._get_compliance_gap_md()
        self.assertIsNotNone(md)
        defn = parse_process_definition("compliance_gap_analysis", md)
        self.assertEqual(defn.name, "compliance_gap_analysis")
        self.assertGreaterEqual(defn.step_count(), 5)
        self.assertIn("legal", defn.doc_types or ["compliance"])

    def test_parse_builtin_contract_review(self):
        from app.naturalsentinel.documents.builtin_processes import (
            get_builtin_definition,
        )
        from app.naturalsentinel.documents.process_engine import (
            parse_process_definition,
        )

        md = get_builtin_definition("contract_review")
        defn = parse_process_definition("contract_review", md)
        self.assertEqual(defn.name, "contract_review")
        self.assertGreaterEqual(defn.step_count(), 8)

        # Step 1 should have instruction and retrieval_query
        step1 = defn.get_step(1)
        self.assertIsNotNone(step1)
        self.assertGreater(len(step1.instruction), 20)
        self.assertGreater(len(step1.retrieval_query), 5)

    def test_parse_builtin_medical_records_review(self):
        from app.naturalsentinel.documents.builtin_processes import (
            get_builtin_definition,
        )
        from app.naturalsentinel.documents.process_engine import (
            parse_process_definition,
        )

        md = get_builtin_definition("medical_records_review")
        defn = parse_process_definition("medical_records_review", md)
        self.assertEqual(defn.name, "medical_records_review")
        self.assertGreaterEqual(defn.step_count(), 6)

    def test_all_builtin_process_names_have_files(self):
        from app.naturalsentinel.documents.builtin_processes import (
            BUILTIN_PROCESS_NAMES,
            get_builtin_definition,
        )

        for name in BUILTIN_PROCESS_NAMES:
            md = get_builtin_definition(name)
            self.assertIsNotNone(md, f"Built-in process {name!r} has no file")
            self.assertIn("## Step 1", md, f"Built-in process {name!r} missing Step 1")

    def _register_compliance_gap(self):
        """Register compliance_gap_analysis into FakeOVClient for testing."""
        md = self._get_compliance_gap_md()
        from app.naturalsentinel.documents.process_engine import register_process

        result = register_process(
            name="compliance_gap_analysis",
            definition_md=md,
            ov_client=self.ov,
            session_db=self.session,
        )
        return result

    def test_register_process_succeeds(self):
        result = self._register_compliance_gap()
        self.assertTrue(result.get("success"), f"register_process failed: {result}")
        self.assertEqual(result["name"], "compliance_gap_analysis")
        self.assertGreaterEqual(result["step_count"], 5)

    def test_register_process_writes_to_ov(self):
        self._register_compliance_gap()
        written = [uri for uri, _ in self.ov.write_calls]
        # Should have written the definition.md to OV
        self.assertTrue(
            any("processes/compliance_gap_analysis" in u for u in written),
            f"Expected OV write under processes/compliance_gap_analysis, got: {written}",
        )

    def test_follow_process_start_returns_session_id(self):
        """follow_process start action with a real process loaded from OV."""
        # Load process definition from built-in file directly (bypasses DB)
        md = self._get_compliance_gap_md()
        from app.naturalsentinel.documents import process_engine as pe
        from app.naturalsentinel.documents.process_engine import (
            parse_process_definition,
        )

        defn = parse_process_definition("compliance_gap_analysis", md)

        # Monkey-patch _load_definition to return our parsed defn
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            result = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                session_id=None,
                action="start",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
        finally:
            pe._load_definition = original

        self.assertNotIn(
            "error", result, f"follow_process returned error: {result.get('error')}"
        )
        self.assertIn("session_id", result)
        self.assertIn("current_step", result)
        step = result["current_step"]
        self.assertIn("step_number", step)
        self.assertEqual(step["step_number"], 1)
        self.assertIn("instruction", step)
        self.assertGreater(len(step["instruction"]), 10)

    def test_follow_process_advance_through_steps(self):
        """Start a session and advance two steps with findings."""
        md = self._get_compliance_gap_md()
        from app.naturalsentinel.documents import process_engine as pe

        defn = pe.parse_process_definition("compliance_gap_analysis", md)
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            # Start
            r1 = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                action="start",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
            session_id = r1["session_id"]
            self.assertEqual(r1["current_step"]["step_number"], 1)

            # Next — pass in findings for step 1
            r2 = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                session_id=session_id,
                action="next",
                step_result={
                    "findings": "SEC Release 33-11216 applies. 17 CFR § 229.106 in scope.",
                    "status": "pass",
                },
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
        finally:
            pe._load_definition = original

        self.assertNotIn("error", r2, f"Step advance failed: {r2.get('error')}")
        # Should now be on step 2
        self.assertEqual(r2["current_step"]["step_number"], 2)
        prog = r2["progress"]
        self.assertGreaterEqual(prog["completed"], 1)

    def test_follow_process_state_persisted_to_ov(self):
        """Execution state JSON is written to OV after each step."""
        md = self._get_compliance_gap_md()
        from app.naturalsentinel.documents import process_engine as pe

        defn = pe.parse_process_definition("compliance_gap_analysis", md)
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            r = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                action="start",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
            session_id = r["session_id"]
        finally:
            pe._load_definition = original

        # State should be in OV
        state_uri = (
            f"viking://sessions/{session_id}/progress/compliance_gap_analysis.json"
        )
        stored = self.ov._store.get(state_uri)
        self.assertIsNotNone(stored, f"Expected state at {state_uri}")
        state_data = json.loads(stored)
        self.assertEqual(state_data["session_id"], session_id)
        self.assertEqual(state_data["process_name"], "compliance_gap_analysis")

    def test_follow_process_complete_action(self):
        """Completing a session returns a completion dict."""
        md = self._get_compliance_gap_md()
        from app.naturalsentinel.documents import process_engine as pe

        defn = pe.parse_process_definition("compliance_gap_analysis", md)
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            r_start = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                action="start",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
            session_id = r_start["session_id"]

            r_complete = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                session_id=session_id,
                action="complete",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
        finally:
            pe._load_definition = original

        self.assertNotIn("error", r_complete)
        self.assertEqual(r_complete["status"], "completed")
        self.assertIn("session_id", r_complete)

    def test_skip_action_advances_step(self):
        """Skip action increments the step counter without storing findings."""
        md = self._get_compliance_gap_md()
        from app.naturalsentinel.documents import process_engine as pe

        defn = pe.parse_process_definition("compliance_gap_analysis", md)
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            r_start = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                action="start",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
            session_id = r_start["session_id"]

            r_skip = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                session_id=session_id,
                action="skip",
                step_result={"findings": "N/A", "status": "skipped"},
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
        finally:
            pe._load_definition = original

        self.assertNotIn("error", r_skip)
        self.assertEqual(r_skip["current_step"]["step_number"], 2)


# ---------------------------------------------------------------------------


class TestSessionMemoryLifecycle(unittest.TestCase):
    """Layer 6 — Triple-write on process completion."""

    def setUp(self):
        self.ov = FakeOVClient()
        self.qdrant = FakeQdrantClient()
        self.session = FakeSession()

        raw_text = load_fixture()
        from app.naturalsentinel.documents.pipeline import ingest_document

        result = ingest_document(
            source_url="",
            file_path="",
            content_b64=__import__("base64").b64encode(raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={},
            ov_client=self.ov,
            qdrant_client=self.qdrant,
        )
        self.doc_id = result["doc_id"]

    def test_complete_writes_ov_summary(self):
        """Process completion writes a session summary to OV."""
        from app.naturalsentinel.documents import process_engine as pe
        from app.naturalsentinel.documents.builtin_processes import (
            get_builtin_definition,
        )

        defn = pe.parse_process_definition(
            "compliance_gap_analysis", get_builtin_definition("compliance_gap_analysis")
        )
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            r_start = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                action="start",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
            session_id = r_start["session_id"]
            pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                session_id=session_id,
                action="complete",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
        finally:
            pe._load_definition = original

        summary_uri = f"viking://sessions/{session_id}/summary.md"
        self.assertIn(
            summary_uri, self.ov._store, "OV summary.md must be written on complete"
        )
        summary = self.ov._store[summary_uri]
        self.assertIn("completed", summary.lower())

    def test_complete_writes_qdrant_session_point(self):
        """Process completion upserts an embedding into ns_sessions."""
        from app.naturalsentinel.documents import process_engine as pe
        from app.naturalsentinel.documents.builtin_processes import (
            get_builtin_definition,
        )
        from app.naturalsentinel.documents.qdrant_service import ensure_collections

        ensure_collections(self.qdrant)
        defn = pe.parse_process_definition(
            "compliance_gap_analysis", get_builtin_definition("compliance_gap_analysis")
        )
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            r_start = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                action="start",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
            session_id = r_start["session_id"]
            pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                session_id=session_id,
                action="complete",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
        finally:
            pe._load_definition = original

        ns_sessions_points = self.qdrant._collections.get("ns_sessions", [])
        self.assertGreater(
            len(ns_sessions_points), 0, "ns_sessions must have a point after completion"
        )
        payloads = [p.payload for p in ns_sessions_points]
        session_payloads = [p for p in payloads if p.get("session_id") == session_id]
        self.assertGreater(
            len(session_payloads),
            0,
            f"No ns_sessions point for session_id={session_id}",
        )

    def test_complete_writes_pg_memory_row(self):
        """Process completion adds an EPISODIC memory row to the fake session."""
        from app.naturalsentinel.documents import process_engine as pe
        from app.naturalsentinel.documents.builtin_processes import (
            get_builtin_definition,
        )

        defn = pe.parse_process_definition(
            "compliance_gap_analysis", get_builtin_definition("compliance_gap_analysis")
        )
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            r_start = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                action="start",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
            session_id = r_start["session_id"]
            pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                session_id=session_id,
                action="complete",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
        finally:
            pe._load_definition = original

        # The fake session's _rows should include a PgMemory row
        from app.naturalsentinel.memory.pg_models import PgMemory

        memory_rows = [r for r in self.session._rows if isinstance(r, PgMemory)]
        self.assertGreater(
            len(memory_rows), 0, "PgMemory row must be added on process completion"
        )
        mem = memory_rows[0]
        self.assertEqual(mem.memory_type, "EPISODIC")
        self.assertIn("compliance_gap_analysis", mem.key)


# ---------------------------------------------------------------------------


class TestStateLevelMonitoring(unittest.TestCase):
    """Block 2 — State-level regulatory monitoring models and sector mappings."""

    def test_industry_sector_enum_has_all_expected_values(self):
        from app.naturalsentinel.models import IndustrySector

        expected = {
            "financial_services",
            "healthcare",
            "insurance",
            "energy_utilities",
            "real_estate",
            "technology",
            "manufacturing",
            "transportation",
        }
        actual = {s.value for s in IndustrySector}
        self.assertTrue(
            expected.issubset(actual),
            f"Missing IndustrySector values: {expected - actual}",
        )

    def test_state_code_enum_has_all_50_states_and_dc(self):
        from app.naturalsentinel.models import StateCode

        codes = {s.value for s in StateCode}
        # Spot-check a few
        for code in ("CA", "NY", "TX", "FL", "DC"):
            self.assertIn(code, codes, f"StateCode missing {code}")
        self.assertGreaterEqual(len(codes), 51)  # 50 states + DC

    def test_jurisdiction_enum(self):
        from app.naturalsentinel.models import Jurisdiction

        self.assertEqual(Jurisdiction.FEDERAL.value, "federal")
        self.assertEqual(Jurisdiction.STATE.value, "state")

    def test_sector_to_federal_domains_mapping(self):
        from app.naturalsentinel.fetchers.state_domains import SECTOR_TO_FEDERAL_DOMAINS

        self.assertIn("financial_services", SECTOR_TO_FEDERAL_DOMAINS)
        self.assertIn("healthcare", SECTOR_TO_FEDERAL_DOMAINS)
        fs_domains = SECTOR_TO_FEDERAL_DOMAINS["financial_services"]
        self.assertIn("sec", fs_domains)
        self.assertIn("cfpb", fs_domains)

    def test_sector_state_agencies_mapping(self):
        from app.naturalsentinel.fetchers.state_domains import SECTOR_STATE_AGENCIES

        self.assertIn("financial_services", SECTOR_STATE_AGENCIES)
        self.assertIn("insurance", SECTOR_STATE_AGENCIES)
        self.assertIn("healthcare", SECTOR_STATE_AGENCIES)

    def test_state_rss_feeds_has_priority_states(self):
        from app.naturalsentinel.fetchers.state_domains import STATE_AGENCY_RSS_FEEDS

        for state in ("CA", "NY", "TX"):
            self.assertIn(
                state, STATE_AGENCY_RSS_FEEDS, f"Missing RSS feeds for {state}"
            )

    def test_regulatory_filing_accepts_state_fields(self):
        from app.naturalsentinel.models import (
            Jurisdiction,
            RegulatoryDomain,
            RegulatoryFiling,
            StateCode,
        )

        filing = RegulatoryFiling(
            id="CA-SEC-2024-001",
            title="California Consumer Financial Protection Law Amendment",
            domain=RegulatoryDomain.SEC,
            source_url="https://dfpi.ca.gov/",
            published_date="2024-01-15",
            raw_text="",
            jurisdiction=Jurisdiction.STATE,
            state_code=StateCode.CA,
            industry_sectors=["financial_services"],
        )
        self.assertEqual(filing.jurisdiction, Jurisdiction.STATE)
        self.assertEqual(filing.state_code, StateCode.CA)
        self.assertEqual(filing.industry_sectors, ["financial_services"])

    def test_expand_domains_uses_sector_mapping(self):
        """_expand_domains adds SEC/CFPB when financial_services sector is given."""
        from app.naturalsentinel.fetchers.base import _expand_domains
        from app.naturalsentinel.models import IndustrySector

        domains = _expand_domains(
            None,
            [IndustrySector.FINANCIAL_SERVICES],
        )
        domain_values = {d.value for d in domains}
        self.assertIn("sec", domain_values)
        self.assertIn("cfpb", domain_values)

    def test_state_fetchers_handle_missing_api_key(self):
        """State fetchers must return empty list (not raise) when API key absent."""
        import os

        os.environ.pop("OPEN_STATES_API_KEY", None)
        from app.naturalsentinel.fetchers.live.open_states import (
            fetch as fetch_open_states,
        )

        result = fetch_open_states(
            state_codes=["CA"], sectors=["financial_services"], since_days=7
        )
        self.assertIsInstance(
            result, list, "open_states.fetch must return a list even without API key"
        )

    def test_csbs_fetch_returns_list(self):
        """CSBS fetcher returns a list (may be empty if network unavailable)."""
        from unittest.mock import patch

        with patch("feedparser.parse", return_value={"entries": []}):
            from app.naturalsentinel.fetchers.live.csbs import fetch

            result = fetch(since_days=7)
        self.assertIsInstance(result, list)

    def test_naic_fetch_returns_list(self):
        from unittest.mock import patch

        with patch("feedparser.parse", return_value={"entries": []}):
            from app.naturalsentinel.fetchers.live.naic import fetch

            result = fetch(since_days=7)
        self.assertIsInstance(result, list)

    def test_nasaa_fetch_returns_list(self):
        from unittest.mock import patch

        with patch("feedparser.parse", return_value={"entries": []}):
            from app.naturalsentinel.fetchers.live.nasaa import fetch

            result = fetch(since_days=7)
        self.assertIsInstance(result, list)


# ---------------------------------------------------------------------------


class TestEndToEndPRDFlow(unittest.TestCase):
    """Full end-to-end smoke test: ingest → retrieve → process → memory commit."""

    def test_full_flow(self):
        """
        Complete PRD flow:
          1. Ingest the real SEC cybersecurity rule fixture
          2. Retrieve context with a relevant query
          3. Parse and register the compliance_gap_analysis process
          4. Start, advance, and complete the process against the ingested doc
          5. Verify session memory was written to all three backends
        """
        import base64

        raw_text = load_fixture()
        ov = FakeOVClient()
        qdrant = FakeQdrantClient()
        session = FakeSession()

        # ── 1. INGEST ────────────────────────────────────────────────────────
        from app.naturalsentinel.documents.pipeline import ingest_document
        from app.naturalsentinel.documents.qdrant_service import ensure_collections

        ensure_collections(qdrant)

        ingest_result = ingest_document(
            source_url="",
            file_path="",
            content_b64=base64.b64encode(raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={"source": "SEC-2023-0726-CYB", "tags": ["cybersecurity", "sec"]},
            ov_client=ov,
            qdrant_client=qdrant,
        )
        self.assertIn("doc_id", ingest_result)
        self.assertGreater(ingest_result["section_count"], 0)
        doc_id = ingest_result["doc_id"]

        # ── 2. RETRIEVE ──────────────────────────────────────────────────────
        from app.naturalsentinel.documents.retrieval import recall_context

        retrieval_result = recall_context(
            query="Form 8-K Item 1.05 material cybersecurity incident disclosure four business days",
            ov_client=ov,
            qdrant_client=qdrant,
            doc_ids=[doc_id],
            token_budget=4096,
            depth="overview",
        )
        self.assertIn("context_blocks", retrieval_result)
        self.assertIn("total_tokens", retrieval_result)
        self.assertGreaterEqual(retrieval_result["total_tokens"], 0)

        # ── 3. REGISTER PROCESS ──────────────────────────────────────────────
        from app.naturalsentinel.documents.builtin_processes import (
            get_builtin_definition,
        )
        from app.naturalsentinel.documents.process_engine import (
            parse_process_definition,
            register_process,
        )

        md = get_builtin_definition("compliance_gap_analysis")
        reg_result = register_process(
            name="compliance_gap_analysis",
            definition_md=md,
            ov_client=ov,
            session_db=session,
        )
        self.assertTrue(reg_result.get("success"), f"Registration failed: {reg_result}")

        # ── 4. EXECUTE PROCESS ───────────────────────────────────────────────
        from app.naturalsentinel.documents import process_engine as pe

        defn = parse_process_definition("compliance_gap_analysis", md)
        original_loader = pe._load_definition
        pe._load_definition = lambda name, session_db: defn

        try:
            r_start = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[doc_id],
                action="start",
                ov_client=ov,
                qdrant_client=qdrant,
                session_db=session,
            )
            session_id = r_start["session_id"]

            # Advance step 1 with findings about the real document
            r_next = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[doc_id],
                session_id=session_id,
                action="next",
                step_result={
                    "findings": (
                        "Applicable regulation: SEC Release 33-11216 / 17 CFR § 229.106. "
                        "Scope: all public company registrants. Effective: December 15, 2023 "
                        "(large accelerated filers). Cybersecurity incident defined, "
                        "materiality threshold per TSC Industries standard."
                    ),
                    "status": "pass",
                },
                ov_client=ov,
                qdrant_client=qdrant,
                session_db=session,
            )
            self.assertEqual(r_next["current_step"]["step_number"], 2)

            # Complete the process
            r_complete = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[doc_id],
                session_id=session_id,
                action="complete",
                ov_client=ov,
                qdrant_client=qdrant,
                session_db=session,
            )
        finally:
            pe._load_definition = original_loader

        self.assertEqual(r_complete["status"], "completed")

        # ── 5. VERIFY SESSION MEMORY TRIPLE-WRITE ────────────────────────────
        # (a) OV: summary.md
        summary_uri = f"viking://sessions/{session_id}/summary.md"
        self.assertIn(summary_uri, ov._store, "OV summary missing")

        # (b) Qdrant: ns_sessions point
        ns_sessions = qdrant._collections.get("ns_sessions", [])
        self.assertGreater(len(ns_sessions), 0, "No ns_sessions points written")

        # (c) PgMemory: EPISODIC row in fake session
        from app.naturalsentinel.memory.pg_models import PgMemory

        memory_rows = [r for r in session._rows if isinstance(r, PgMemory)]
        self.assertGreater(len(memory_rows), 0, "No PgMemory EPISODIC row written")
        self.assertEqual(memory_rows[0].memory_type, "EPISODIC")

        # ── Verify real filing is in sample data ─────────────────────────────
        from app.naturalsentinel.fetchers.sample_data import (
            MOCK_ANALYSES,
            SAMPLE_FILINGS,
        )

        real_filing = next(
            (f for f in SAMPLE_FILINGS if f["id"] == "SEC-2023-0726-CYB"), None
        )
        self.assertIsNotNone(
            real_filing, "Real SEC-2023-0726-CYB filing must be in SAMPLE_FILINGS"
        )
        self.assertIn("SEC-2023-0726-CYB", MOCK_ANALYSES)


# ===========================================================================
# TestPostgresDocumentLayer
# Verifies that all three PG table writes happen correctly via FakeSession:
#   PgDocument on ingest, PgProcessDefinition on register, PgProcessExecution on follow.
# ===========================================================================


class TestPostgresDocumentLayer(unittest.TestCase):
    """PgDocument is written on ingest; PgProcessDefinition and PgProcessExecution
    are written on register_process / follow_process when session_db is provided."""

    def setUp(self):
        self.raw_text = load_fixture()
        self.ov = FakeOVClient()
        self.qdrant = FakeQdrantClient()
        self.session = FakeSession()

    def _ingest(self, session=None):
        from app.naturalsentinel.documents.pipeline import ingest_document

        return ingest_document(
            content_b64=__import__("base64").b64encode(self.raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={"tags": ["cybersecurity"]},
            ov_client=self.ov,
            qdrant_client=self.qdrant,
            session_db=session or self.session,
        )

    def test_ingest_creates_pg_document(self):
        from app.naturalsentinel.memory.pg_models import PgDocument

        self._ingest()
        docs = [r for r in self.session._rows if isinstance(r, PgDocument)]
        self.assertEqual(len(docs), 1, "Exactly one PgDocument must be added on ingest")

    def test_pg_document_doc_id_matches_result(self):
        from app.naturalsentinel.memory.pg_models import PgDocument

        result = self._ingest()
        doc = next(r for r in self.session._rows if isinstance(r, PgDocument))
        self.assertEqual(doc.doc_id, result["doc_id"])

    def test_pg_document_fields_populated(self):
        from app.naturalsentinel.memory.pg_models import PgDocument

        result = self._ingest()
        doc = next(r for r in self.session._rows if isinstance(r, PgDocument))
        self.assertEqual(doc.doc_type, result["doc_type"])
        self.assertTrue(doc.viking_uri.startswith("viking://documents/"))
        self.assertGreater(doc.section_count, 0)
        self.assertEqual(doc.status, "ready")

    def test_pg_document_session_committed(self):
        self._ingest()
        self.assertTrue(
            self.session.committed, "Session must be committed after PgDocument persist"
        )

    def test_pg_process_definition_written_on_register(self):
        from app.naturalsentinel.documents.builtin_processes import (
            get_builtin_definition,
        )
        from app.naturalsentinel.documents.process_engine import register_process
        from app.naturalsentinel.memory.pg_models import PgProcessDefinition

        md = get_builtin_definition("contract_review")
        register_process(
            name="contract_review",
            definition_md=md,
            ov_client=self.ov,
            session_db=self.session,
        )
        defs = [r for r in self.session._rows if isinstance(r, PgProcessDefinition)]
        self.assertEqual(
            len(defs), 1, "One PgProcessDefinition must be added on register_process"
        )
        self.assertEqual(defs[0].name, "contract_review")
        self.assertGreater(defs[0].step_count, 0)

    def test_pg_process_execution_written_on_follow_start(self):
        from app.naturalsentinel.documents import process_engine as pe
        from app.naturalsentinel.documents.builtin_processes import (
            get_builtin_definition,
        )
        from app.naturalsentinel.memory.pg_models import PgProcessExecution

        defn = pe.parse_process_definition(
            "compliance_gap_analysis", get_builtin_definition("compliance_gap_analysis")
        )
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            result = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=["pg-test-doc-001"],
                action="start",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
        finally:
            pe._load_definition = original

        execs = [r for r in self.session._rows if isinstance(r, PgProcessExecution)]
        self.assertGreater(
            len(execs), 0, "PgProcessExecution must be created on follow_process start"
        )
        ex = execs[0]
        self.assertEqual(ex.session_id, result["session_id"])
        self.assertEqual(ex.process_name, "compliance_gap_analysis")
        self.assertIn("pg-test-doc-001", ex.doc_ids)
        self.assertEqual(ex.current_step, 1)
        self.assertGreater(ex.total_steps, 0)

    def test_pg_process_execution_updated_on_advance(self):
        from app.naturalsentinel.documents import process_engine as pe
        from app.naturalsentinel.documents.builtin_processes import (
            get_builtin_definition,
        )
        from app.naturalsentinel.memory.pg_models import PgProcessExecution

        defn = pe.parse_process_definition(
            "compliance_gap_analysis", get_builtin_definition("compliance_gap_analysis")
        )
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            r_start = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=["pg-test-doc-002"],
                action="start",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
            pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=["pg-test-doc-002"],
                session_id=r_start["session_id"],
                action="next",
                step_result={
                    "findings": "17 CFR § 229.106 in scope.",
                    "status": "pass",
                },
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=self.session,
            )
        finally:
            pe._load_definition = original

        # After start + advance there are two PgProcessExecution rows (upsert path adds new on mock)
        execs = [r for r in self.session._rows if isinstance(r, PgProcessExecution)]
        self.assertGreaterEqual(len(execs), 1)


# ===========================================================================
# TestOVReadbackFidelity
# After the FakeOVClient path fix, verifies that everything the pipeline
# writes to OV is readable back through the correct client methods.
# ===========================================================================


class TestOVReadbackFidelity(unittest.TestCase):
    """Content written by the pipeline to OV is readable via abstract() / overview() / read()."""

    def setUp(self):
        self.raw_text = load_fixture()
        self.ov = FakeOVClient()
        self.qdrant = FakeQdrantClient()

        from app.naturalsentinel.documents.pipeline import ingest_document

        result = ingest_document(
            content_b64=__import__("base64").b64encode(self.raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={},
            ov_client=self.ov,
            qdrant_client=self.qdrant,
        )
        self.doc_id = result["doc_id"]
        self.doc_uri = f"viking://documents/{self.doc_id}"

    def test_abstract_md_uri_written(self):
        uri = f"{self.doc_uri}/.abstract.md"
        self.assertIn(uri, self.ov._store, ".abstract.md not written for document root")
        self.assertGreater(len(self.ov._store[uri]), 0)

    def test_overview_md_uri_written(self):
        uri = f"{self.doc_uri}/.overview.md"
        self.assertIn(uri, self.ov._store, ".overview.md not written for document root")
        self.assertGreater(len(self.ov._store[uri]), 0)

    def test_meta_json_contains_doc_id(self):
        uri = f"{self.doc_uri}/meta.json"
        self.assertIn(uri, self.ov._store, "meta.json not written")
        self.assertIn(self.doc_id, self.ov._store[uri])

    def test_section_content_md_written(self):
        """At least one section has a content.md (full L2 text) in OV."""
        content_uris = [
            k
            for k in self.ov._store
            if k.startswith(self.doc_uri) and k.endswith("/content.md")
        ]
        self.assertGreater(
            len(content_uris), 0, "No content.md section files written to OV"
        )
        # Verify bodies are non-trivial
        for uri in content_uris[:3]:
            self.assertGreater(len(self.ov._store[uri]), 20)

    def test_ov_abstract_method_returns_doc_abstract(self):
        """abstract(doc_uri) returns the .abstract.md content written by the pipeline."""
        content = self.ov.abstract(self.doc_uri)
        self.assertGreater(
            len(content), 0, "abstract() returned empty string — path mismatch?"
        )

    def test_ov_overview_method_returns_doc_overview(self):
        """overview(doc_uri) returns the .overview.md content written by the pipeline."""
        content = self.ov.overview(self.doc_uri)
        self.assertGreater(
            len(content), 0, "overview() returned empty string — path mismatch?"
        )

    def test_section_node_abstract_readable(self):
        """At least one section node's abstract is readable via abstract(section_uri)."""
        section_uris = [
            k[: -len("/.abstract.md")]
            for k in self.ov._store
            if k.startswith(self.doc_uri)
            and k.endswith("/.abstract.md")
            and k != f"{self.doc_uri}/.abstract.md"  # skip the doc-level one
        ]
        self.assertGreater(
            len(section_uris), 0, "No per-section .abstract.md files found"
        )
        for sec_uri in section_uris[:3]:
            content = self.ov.abstract(sec_uri)
            self.assertGreater(len(content), 0, f"abstract({sec_uri!r}) returned empty")

    def test_retrieval_context_blocks_non_empty_after_fix(self):
        """With the fixed FakeOVClient, recall_context returns blocks with actual content."""
        from app.naturalsentinel.documents.retrieval import recall_context

        result = recall_context(
            query="Form 8-K Item 1.05 cybersecurity incident",
            ov_client=self.ov,
            qdrant_client=self.qdrant,
            doc_ids=[self.doc_id],
            depth="abstract",
            token_budget=2048,
        )
        non_empty = [
            b for b in result["context_blocks"] if b.get("content", "").strip()
        ]
        self.assertGreater(len(non_empty), 0, "All retrieval blocks have empty content")


# ===========================================================================
# TestCrossDatabaseConsistency
# A single ingest call must populate OV, Qdrant, and PG with the same doc_id.
# ===========================================================================


class TestCrossDatabaseConsistency(unittest.TestCase):
    """doc_id, viking_uri, and section_count must be consistent across all three stores."""

    def setUp(self):
        self.raw_text = load_fixture()
        self.ov = FakeOVClient()
        self.qdrant = FakeQdrantClient()
        self.session = FakeSession()

        from app.naturalsentinel.documents.pipeline import ingest_document
        from app.naturalsentinel.documents.qdrant_service import ensure_collections

        ensure_collections(self.qdrant)
        self.result = ingest_document(
            content_b64=__import__("base64").b64encode(self.raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={"source": "cross-db-test"},
            ov_client=self.ov,
            qdrant_client=self.qdrant,
            session_db=self.session,
        )
        self.doc_id = self.result["doc_id"]

    def test_all_three_stores_populated(self):
        from app.naturalsentinel.memory.pg_models import PgDocument

        ov_writes = [u for u, _ in self.ov.write_calls if self.doc_id in u]
        qdrant_points = self.qdrant._collections.get("ns_documents", [])
        pg_docs = [r for r in self.session._rows if isinstance(r, PgDocument)]

        self.assertGreater(len(ov_writes), 0, "OV has no writes for this doc_id")
        self.assertGreater(len(qdrant_points), 0, "Qdrant ns_documents is empty")
        self.assertGreater(len(pg_docs), 0, "PG has no PgDocument row")

    def test_ov_writes_under_doc_namespace(self):
        expected_prefix = f"viking://documents/{self.doc_id}"
        doc_writes = [
            u for u, _ in self.ov.write_calls if u.startswith(expected_prefix)
        ]
        self.assertGreater(len(doc_writes), 0, f"No OV writes under {expected_prefix}")

    def test_qdrant_points_carry_correct_doc_id(self):
        points = self.qdrant._collections.get("ns_documents", [])
        self.assertGreater(len(points), 0)
        for pt in points:
            self.assertEqual(
                pt.payload.get("doc_id"),
                self.doc_id,
                f"Point {pt.id} has wrong doc_id: {pt.payload.get('doc_id')!r}",
            )

    def test_pg_document_doc_id_matches(self):
        from app.naturalsentinel.memory.pg_models import PgDocument

        doc = next(r for r in self.session._rows if isinstance(r, PgDocument))
        self.assertEqual(doc.doc_id, self.doc_id)

    def test_pg_viking_uri_matches_ov_root(self):
        from app.naturalsentinel.memory.pg_models import PgDocument

        doc = next(r for r in self.session._rows if isinstance(r, PgDocument))
        expected = f"viking://documents/{self.doc_id}"
        self.assertTrue(
            doc.viking_uri.startswith(expected),
            f"PgDocument.viking_uri {doc.viking_uri!r} doesn't match OV root {expected!r}",
        )

    def test_qdrant_viking_uris_reference_correct_doc(self):
        """Every Qdrant point's viking_uri must be under the expected OV namespace."""
        expected_prefix = f"viking://documents/{self.doc_id}"
        points = self.qdrant._collections.get("ns_documents", [])
        for pt in points:
            uri = pt.payload.get("viking_uri", "")
            self.assertTrue(
                uri.startswith(expected_prefix),
                f"Qdrant point viking_uri {uri!r} not under {expected_prefix!r}",
            )

    def test_section_count_consistent_across_result_and_pg(self):
        from app.naturalsentinel.memory.pg_models import PgDocument

        doc = next(r for r in self.session._rows if isinstance(r, PgDocument))
        self.assertEqual(
            doc.section_count,
            self.result["section_count"],
            "PgDocument.section_count must match ingest result section_count",
        )

    def test_qdrant_point_count_within_expected_range(self):
        """Each section generates up to 3 Qdrant points (L0, L1, L2)."""
        points = self.qdrant._collections.get("ns_documents", [])
        sc = self.result["section_count"]
        self.assertGreaterEqual(
            len(points),
            sc,
            "Fewer Qdrant points than sections (need at least 1 per section)",
        )
        self.assertLessEqual(
            len(points), sc * 3 + 5, "Too many Qdrant points relative to section count"
        )


# ===========================================================================
# TestSessionTripleWriteConsistency
# A single `action=complete` call must write the same session_id to all three
# backends: OV summary.md, Qdrant ns_sessions, and PgMemory.
# ===========================================================================


class TestSessionTripleWriteConsistency(unittest.TestCase):
    """After process completion the same session_id appears in OV, Qdrant, and PG."""

    def test_complete_all_three_stores_share_session_id(self):
        from app.naturalsentinel.documents import process_engine as pe
        from app.naturalsentinel.documents.builtin_processes import (
            get_builtin_definition,
        )
        from app.naturalsentinel.documents.qdrant_service import ensure_collections
        from app.naturalsentinel.memory.pg_models import PgMemory

        ov = FakeOVClient()
        qdrant = FakeQdrantClient()
        session = FakeSession()
        ensure_collections(qdrant)

        defn = pe.parse_process_definition(
            "compliance_gap_analysis", get_builtin_definition("compliance_gap_analysis")
        )
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            r_start = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=["triple-write-doc"],
                action="start",
                ov_client=ov,
                qdrant_client=qdrant,
                session_db=session,
            )
            session_id = r_start["session_id"]

            pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=["triple-write-doc"],
                session_id=session_id,
                action="complete",
                ov_client=ov,
                qdrant_client=qdrant,
                session_db=session,
            )
        finally:
            pe._load_definition = original

        # ── 1. OV ─────────────────────────────────────────────────────────────
        summary_uri = f"viking://sessions/{session_id}/summary.md"
        self.assertIn(summary_uri, ov._store, "OV summary.md not written")
        self.assertIn(
            session_id,
            ov._store[summary_uri],
            "session_id absent from OV summary content",
        )

        # ── 2. Qdrant ns_sessions ─────────────────────────────────────────────
        ns_sessions = qdrant._collections.get("ns_sessions", [])
        self.assertGreater(
            len(ns_sessions), 0, "Qdrant ns_sessions empty after complete"
        )
        matching_qdrant = [
            p for p in ns_sessions if p.payload.get("session_id") == session_id
        ]
        self.assertEqual(
            len(matching_qdrant),
            1,
            f"Expected 1 ns_sessions point with session_id={session_id!r}",
        )

        # ── 3. PgMemory EPISODIC ──────────────────────────────────────────────
        mem_rows = [r for r in session._rows if isinstance(r, PgMemory)]
        self.assertGreater(len(mem_rows), 0, "No PgMemory row after complete")
        matching_pg = [r for r in mem_rows if session_id in r.key]
        self.assertEqual(
            len(matching_pg),
            1,
            f"No PgMemory row with session_id={session_id!r} in key",
        )

        # ── Cross-assertion: all three reference the identical session_id ─────
        self.assertEqual(
            matching_qdrant[0].payload["session_id"],
            matching_pg[0].content["session_id"],
            "Qdrant and PG must store the same session_id value",
        )

    def test_complete_qdrant_point_payload_fields(self):
        """ns_sessions point has expected payload shape."""
        from app.naturalsentinel.documents import process_engine as pe
        from app.naturalsentinel.documents.builtin_processes import (
            get_builtin_definition,
        )
        from app.naturalsentinel.documents.qdrant_service import ensure_collections

        ov = FakeOVClient()
        qdrant = FakeQdrantClient()
        session = FakeSession()
        ensure_collections(qdrant)

        defn = pe.parse_process_definition(
            "contract_review", get_builtin_definition("contract_review")
        )
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            r = pe.follow_process(
                process_name="contract_review",
                doc_ids=["payload-shape-doc"],
                action="start",
                ov_client=ov,
                qdrant_client=qdrant,
                session_db=session,
            )
            session_id = r["session_id"]
            pe.follow_process(
                process_name="contract_review",
                doc_ids=["payload-shape-doc"],
                session_id=session_id,
                action="complete",
                ov_client=ov,
                qdrant_client=qdrant,
                session_db=session,
            )
        finally:
            pe._load_definition = original

        point = next(
            p
            for p in qdrant._collections.get("ns_sessions", [])
            if p.payload.get("session_id") == session_id
        )
        for key in ("session_id", "process_name", "doc_ids", "completed", "summary"):
            self.assertIn(
                key, point.payload, f"ns_sessions point missing payload key: {key!r}"
            )


# ===========================================================================
# TestProcessStateResume
# State persisted to OV after `start` must be reloadable in a subsequent call
# using a fresh FakeSession (simulating a new HTTP request with no DB rows).
# ===========================================================================


class TestProcessStateResume(unittest.TestCase):
    """follow_process resumes an in-progress session by loading state from OV."""

    def setUp(self):
        self.ov = FakeOVClient()
        self.qdrant = FakeQdrantClient()

        raw_text = load_fixture()
        from app.naturalsentinel.documents.pipeline import ingest_document

        result = ingest_document(
            content_b64=__import__("base64").b64encode(raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={},
            ov_client=self.ov,
            qdrant_client=self.qdrant,
        )
        self.doc_id = result["doc_id"]

    def _defn(self):
        from app.naturalsentinel.documents import process_engine as pe
        from app.naturalsentinel.documents.builtin_processes import (
            get_builtin_definition,
        )

        return pe.parse_process_definition(
            "compliance_gap_analysis", get_builtin_definition("compliance_gap_analysis")
        )

    def test_resume_advances_to_step_2(self):
        """Start a session, then resume with a fresh FakeSession — step 2 is returned."""
        from app.naturalsentinel.documents import process_engine as pe

        defn = self._defn()
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            # Request 1: start
            r_start = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                action="start",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=FakeSession(),
            )
            session_id = r_start["session_id"]
            self.assertEqual(r_start["current_step"]["step_number"], 1)

            # Request 2: new FakeSession (empty DB) — state must come from OV
            r_next = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                session_id=session_id,
                action="next",
                step_result={"findings": "Requirements confirmed.", "status": "pass"},
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=FakeSession(),  # fresh — no DB rows
            )
        finally:
            pe._load_definition = original

        self.assertNotIn("error", r_next, f"Resume failed: {r_next.get('error')}")
        self.assertEqual(r_next["current_step"]["step_number"], 2)

    def test_step_findings_survive_ov_round_trip(self):
        """Findings recorded in step 1 are present in state after OV reload."""
        from app.naturalsentinel.documents import process_engine as pe

        defn = self._defn()
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            r_start = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                action="start",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=FakeSession(),
            )
            session_id = r_start["session_id"]

            # Advance step 1 with a unique sentinel string
            pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                session_id=session_id,
                action="next",
                step_result={"findings": "SENTINEL_FINDING_XYZ", "status": "flagged"},
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=FakeSession(),
            )

            # Request 3: fresh session, status action — must load from OV
            r_status = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                session_id=session_id,
                action="status",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=FakeSession(),
            )
        finally:
            pe._load_definition = original

        all_findings = " ".join(r["findings"] for r in r_status.get("step_records", []))
        self.assertIn(
            "SENTINEL_FINDING_XYZ",
            all_findings,
            "Step findings must survive OV round-trip",
        )

    def test_unknown_session_id_returns_error(self):
        """follow_process with an unknown session_id returns an error dict, never raises."""
        from app.naturalsentinel.documents import process_engine as pe

        defn = self._defn()
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            result = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                session_id="completely-nonexistent-session-id-00000",
                action="next",
                step_result={"findings": "N/A", "status": "pass"},
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=FakeSession(),
            )
        finally:
            pe._load_definition = original

        self.assertIn("error", result, "Unknown session_id must return an error dict")
        self.assertNotIsInstance(result, Exception)

    def test_ov_state_file_uri_is_deterministic(self):
        """State file is always at viking://sessions/{session_id}/progress/{name}.json."""
        from app.naturalsentinel.documents import process_engine as pe

        defn = self._defn()
        original = pe._load_definition
        pe._load_definition = lambda name, session_db: defn
        try:
            r = pe.follow_process(
                process_name="compliance_gap_analysis",
                doc_ids=[self.doc_id],
                action="start",
                ov_client=self.ov,
                qdrant_client=self.qdrant,
                session_db=FakeSession(),
            )
            session_id = r["session_id"]
        finally:
            pe._load_definition = original

        expected_uri = (
            f"viking://sessions/{session_id}/progress/compliance_gap_analysis.json"
        )
        self.assertIn(
            expected_uri, self.ov._store, f"State file not found at {expected_uri}"
        )


# ===========================================================================
# TestRRFDeduplication
# Unit tests for _reciprocal_rank_fusion — the merge function that combines
# Qdrant kNN results with OpenViking hierarchical results.
# ===========================================================================


class TestRRFDeduplication(unittest.TestCase):
    """Reciprocal Rank Fusion correctness: deduplication, scoring, and ordering."""

    def _r(self, uri: str, score: float = 0.9, source: str = "qdrant") -> dict:
        return {
            "viking_uri": uri,
            "section_path": uri,
            "score": score,
            "doc_id": "doc-001",
            "source": source,
            "payload": {"viking_uri": uri, "abstract": f"Content at {uri}"},
        }

    def test_same_uri_deduplicated_to_one_result(self):
        from app.naturalsentinel.documents.retrieval import _reciprocal_rank_fusion

        uri = "viking://documents/doc-001/article_i"
        merged = _reciprocal_rank_fusion(
            [self._r(uri, score=0.95)],
            [self._r(uri, score=0.80, source="openviking")],
        )
        self.assertEqual(
            len(merged),
            1,
            "Same URI from both sources must be deduplicated to one entry",
        )

    def test_cross_source_uri_scores_higher_than_single_source(self):
        """URI appearing in both ranked lists gets higher RRF score than a URI in only one."""
        from app.naturalsentinel.documents.retrieval import _reciprocal_rank_fusion

        shared = "viking://documents/doc-001/shared"
        unique = "viking://documents/doc-001/unique"

        merged = _reciprocal_rank_fusion(
            [self._r(shared), self._r(unique)],
            [self._r(shared, source="openviking")],
        )
        scores = {m["payload"]["viking_uri"]: m["rrf_score"] for m in merged}
        self.assertGreater(
            scores[shared],
            scores[unique],
            "URI in both sources must outrank URI in only one source",
        )

    def test_empty_both_inputs_returns_empty(self):
        from app.naturalsentinel.documents.retrieval import _reciprocal_rank_fusion

        self.assertEqual(_reciprocal_rank_fusion([], []), [])

    def test_single_source_preserves_all_uris(self):
        from app.naturalsentinel.documents.retrieval import _reciprocal_rank_fusion

        uris = [f"viking://doc/s{i}" for i in range(5)]
        merged = _reciprocal_rank_fusion([self._r(u) for u in uris], [])
        self.assertEqual(len(merged), 5)
        self.assertEqual({m["payload"]["viking_uri"] for m in merged}, set(uris))

    def test_union_of_unique_uris_from_both_sources(self):
        from app.naturalsentinel.documents.retrieval import _reciprocal_rank_fusion

        q_uris = [f"viking://doc/q{i}" for i in range(3)]
        ov_uris = [f"viking://doc/ov{i}" for i in range(3)]
        merged = _reciprocal_rank_fusion(
            [self._r(u) for u in q_uris],
            [self._r(u, source="openviking") for u in ov_uris],
        )
        self.assertEqual(
            {m["payload"]["viking_uri"] for m in merged}, set(q_uris) | set(ov_uris)
        )

    def test_output_sorted_by_rrf_score_descending(self):
        from app.naturalsentinel.documents.retrieval import _reciprocal_rank_fusion

        qdrant = [self._r(f"viking://doc/s{i}") for i in range(5)]
        ov = [self._r(f"viking://doc/s{i}", source="openviking") for i in range(3)]
        merged = _reciprocal_rank_fusion(qdrant, ov)
        scores = [m["rrf_score"] for m in merged]
        self.assertEqual(
            scores, sorted(scores, reverse=True), "RRF output must be sorted descending"
        )

    def test_rrf_score_attached_to_each_result(self):
        from app.naturalsentinel.documents.retrieval import _reciprocal_rank_fusion

        merged = _reciprocal_rank_fusion(
            [self._r("viking://doc/a")],
            [self._r("viking://doc/b", source="openviking")],
        )
        for item in merged:
            self.assertIn("rrf_score", item)
            self.assertGreater(item["rrf_score"], 0.0)

    def test_top_ranked_shared_uri_is_first_in_output(self):
        """URI ranked #1 in both lists should be the first result."""
        from app.naturalsentinel.documents.retrieval import _reciprocal_rank_fusion

        top = "viking://doc/top"
        other_q = "viking://doc/q_only"
        other_ov = "viking://doc/ov_only"

        merged = _reciprocal_rank_fusion(
            [self._r(top), self._r(other_q)],
            [self._r(top, source="openviking"), self._r(other_ov, source="openviking")],
        )
        self.assertEqual(
            merged[0]["payload"]["viking_uri"],
            top,
            "Top shared URI must be first result",
        )


# ---------------------------------------------------------------------------
# TestSourceProvenanceChain
# Verifies that source_url and doc_id survive the full ingest pipeline and
# are recoverable at every layer: OV meta.json → Qdrant payload → recall block.
# ---------------------------------------------------------------------------


class TestSourceProvenanceChain(unittest.TestCase):
    """Source attribution: source_url and doc_id are preserved through all three databases."""

    _SOURCE_URL = (
        "https://federalregister.gov/2023/08/04/sec-cybersecurity-rule-33-11216"
    )

    def setUp(self):
        from unittest.mock import patch

        self.ov = FakeOVClient()
        self.qdrant = FakeQdrantClient()
        raw_text = load_fixture()

        from app.naturalsentinel.documents.pipeline import ingest_document
        from app.naturalsentinel.documents.qdrant_service import ensure_collections

        ensure_collections(self.qdrant)
        # Patch _fetch_url so source_url path returns the fixture content instead of HTTP
        with patch(
            "app.naturalsentinel.documents.pipeline._fetch_url",
            return_value=(raw_text.encode(), "sec-cybersecurity-rule.txt"),
        ):
            result = ingest_document(
                source_url=self._SOURCE_URL,
                content_type="text/plain",
                doc_type="compliance",
                metadata={"tags": ["cybersecurity", "sec"]},
                ov_client=self.ov,
                qdrant_client=self.qdrant,
            )
        self.doc_id = result["doc_id"]

    def test_ov_meta_json_contains_source_url(self):
        """OV meta.json written at ingest time must embed the original source_url."""
        meta_uri = f"viking://documents/{self.doc_id}/meta.json"
        meta_raw = self.ov.read(meta_uri)
        self.assertIn(
            self._SOURCE_URL,
            meta_raw,
            "meta.json must contain the ingest-time source_url",
        )

    def test_ov_meta_json_contains_doc_id(self):
        """meta.json must embed the doc_id so OV is self-describing."""
        meta_uri = f"viking://documents/{self.doc_id}/meta.json"
        meta_raw = self.ov.read(meta_uri)
        self.assertIn(self.doc_id, meta_raw)

    def test_qdrant_points_contain_source_url_in_payload(self):
        """Every Qdrant point written during ingest must carry source_url in its payload."""
        points = self.qdrant._collections.get("ns_documents", [])
        self.assertGreater(len(points), 0, "At least one point must have been upserted")
        for pt in points:
            self.assertEqual(
                pt.payload.get("source_url"),
                self._SOURCE_URL,
                f"Point {pt.id} payload missing correct source_url",
            )

    def test_qdrant_points_contain_doc_id_in_payload(self):
        """Every Qdrant point must carry the doc_id that links back to PG / OV."""
        points = self.qdrant._collections.get("ns_documents", [])
        for pt in points:
            self.assertEqual(
                pt.payload.get("doc_id"),
                self.doc_id,
                f"Point {pt.id} payload missing correct doc_id",
            )

    def test_qdrant_points_contain_viking_uri_in_payload(self):
        """Qdrant payload viking_uri must start with the document root URI."""
        expected_prefix = f"viking://documents/{self.doc_id}"
        points = self.qdrant._collections.get("ns_documents", [])
        for pt in points:
            uri = pt.payload.get("viking_uri", "")
            self.assertTrue(
                uri.startswith(expected_prefix),
                f"Point {pt.id} viking_uri '{uri}' does not start with '{expected_prefix}'",
            )

    def test_recall_blocks_carry_doc_id(self):
        """recall_context blocks must carry the doc_id so callers can look up source_url."""
        from app.naturalsentinel.documents.retrieval import recall_context

        result = recall_context(
            query="cybersecurity incident disclosure four business days",
            ov_client=self.ov,
            qdrant_client=self.qdrant,
            doc_ids=[self.doc_id],
            depth="abstract",
        )
        blocks = result["context_blocks"]
        self.assertGreater(len(blocks), 0, "Expected at least one context block")
        for block in blocks:
            if block.get("doc_id"):
                self.assertEqual(block["doc_id"], self.doc_id)

    def test_recall_blocks_uri_starts_with_document_root(self):
        """Block URI must be rooted at viking://documents/{doc_id}/... so it's traceable."""
        from app.naturalsentinel.documents.retrieval import recall_context

        result = recall_context(
            query="Form 8-K Item 1.05 material cybersecurity",
            ov_client=self.ov,
            qdrant_client=self.qdrant,
            doc_ids=[self.doc_id],
            depth="abstract",
        )
        expected_prefix = f"viking://documents/{self.doc_id}"
        for block in result["context_blocks"]:
            uri = block.get("uri", "")
            if uri:
                self.assertTrue(
                    uri.startswith(expected_prefix),
                    f"Block URI '{uri}' does not start with expected prefix '{expected_prefix}'",
                )

    def test_source_url_recoverable_via_qdrant_payload_lookup(self):
        """Given a block's doc_id, the source_url can be recovered from Qdrant point payloads."""
        from app.naturalsentinel.documents.retrieval import recall_context

        result = recall_context(
            query="materiality determination cybersecurity",
            ov_client=self.ov,
            qdrant_client=self.qdrant,
            doc_ids=[self.doc_id],
            depth="abstract",
        )
        blocks = result["context_blocks"]
        self.assertGreater(len(blocks), 0)

        # Simulate what a caller would do: take block's doc_id, find Qdrant points, recover source_url
        block_doc_id = blocks[0]["doc_id"]
        points = [
            pt
            for pt in self.qdrant._collections.get("ns_documents", [])
            if pt.payload.get("doc_id") == block_doc_id
        ]
        self.assertGreater(
            len(points), 0, "At least one Qdrant point must match block's doc_id"
        )
        recovered_url = points[0].payload.get("source_url", "")
        self.assertEqual(
            recovered_url,
            self._SOURCE_URL,
            "source_url recovered from Qdrant payload must match original",
        )


# ---------------------------------------------------------------------------
# TestQueryToSourceMaterial
# End-to-end hermetic test: ingest a known regulation → ask a question about
# a specific changed rule → verify the response carries the correct source text.
# ---------------------------------------------------------------------------


class TestQueryToSourceMaterial(unittest.TestCase):
    """Question → database flow → correct source regulation material."""

    def setUp(self):
        import base64

        self.source_url = "https://federalregister.gov/2023/08/04/sec-cyber-rule"
        self.ov = FakeOVClient()
        self.qdrant = FakeQdrantClient()
        raw_text = load_fixture()

        from app.naturalsentinel.documents.pipeline import ingest_document
        from app.naturalsentinel.documents.qdrant_service import ensure_collections

        ensure_collections(self.qdrant)
        # Use content_b64 path here (not source_url) so the fixture content is ingested directly
        result = ingest_document(
            content_b64=base64.b64encode(raw_text.encode()).decode(),
            content_type="text/plain",
            doc_type="compliance",
            metadata={"file_name": "sec-cybersecurity-rule.txt"},
            ov_client=self.ov,
            qdrant_client=self.qdrant,
        )
        self.doc_id = result["doc_id"]

    def test_query_returns_blocks_with_relevant_content(self):
        """Querying about 'four business days' returns blocks whose content relates to that rule."""
        from app.naturalsentinel.documents.retrieval import recall_context

        result = recall_context(
            query="four business days material cybersecurity incident disclosure Form 8-K",
            ov_client=self.ov,
            qdrant_client=self.qdrant,
            doc_ids=[self.doc_id],
            depth="overview",
        )
        blocks = result["context_blocks"]
        self.assertGreater(
            len(blocks), 0, "Query must return at least one context block"
        )

        # At least one block must have non-empty content
        non_empty = [b for b in blocks if b.get("content", "").strip()]
        self.assertGreater(
            len(non_empty), 0, "At least one block must have non-empty content"
        )

    def test_query_blocks_contain_text_from_source_document(self):
        """Block content must include text that originated in the ingested regulation."""
        from app.naturalsentinel.documents.retrieval import recall_context

        result = recall_context(
            query="disclosure obligation registrant cybersecurity incident material",
            ov_client=self.ov,
            qdrant_client=self.qdrant,
            doc_ids=[self.doc_id],
            depth="overview",
        )
        all_content = " ".join(
            b.get("content", "") for b in result["context_blocks"]
        ).lower()
        # The fixture contains these phrases verbatim — verify at least one surfaces
        source_phrases = [
            "cybersecurity",
            "registrant",
            "disclosure",
        ]
        for phrase in source_phrases:
            self.assertIn(
                phrase,
                all_content,
                f"Expected source phrase '{phrase}' not found in any context block",
            )

    def test_query_scoped_to_doc_id_excludes_other_documents(self):
        """Querying with a different doc_id must return no blocks from our ingested doc."""
        import base64

        from app.naturalsentinel.documents.pipeline import ingest_document
        from app.naturalsentinel.documents.retrieval import recall_context

        # Ingest a second distinct document via content_b64 (no network)
        other_text = "Simple regulatory notice. Section 1. This rule has no cybersecurity content."
        other_result = ingest_document(
            content_b64=base64.b64encode(other_text.encode()).decode(),
            content_type="text/plain",
            doc_type="notice",
            metadata={"file_name": "other-rule.txt"},
            ov_client=self.ov,
            qdrant_client=self.qdrant,
        )
        other_doc_id = other_result["doc_id"]

        # Query scoped to the other doc should not return our cybersecurity doc's content
        result = recall_context(
            query="four business days material cybersecurity incident",
            ov_client=self.ov,
            qdrant_client=self.qdrant,
            doc_ids=[other_doc_id],
            depth="overview",
        )
        for block in result["context_blocks"]:
            self.assertNotEqual(
                block.get("doc_id"),
                self.doc_id,
                "Blocks scoped to other_doc_id must not reference original doc_id",
            )

    def test_query_returns_non_zero_total_tokens(self):
        """Non-empty result must report a positive token count."""
        from app.naturalsentinel.documents.retrieval import recall_context

        result = recall_context(
            query="board oversight cybersecurity risk annual disclosure",
            ov_client=self.ov,
            qdrant_client=self.qdrant,
            doc_ids=[self.doc_id],
            depth="overview",
        )
        if result["context_blocks"]:
            self.assertGreater(result["total_tokens"], 0)

    def test_retrieval_trajectory_attributes_to_correct_sources(self):
        """Trajectory metadata must show qdrant_candidates > 0 when Qdrant has the doc."""
        from app.naturalsentinel.documents.retrieval import recall_context

        result = recall_context(
            query="annual report cybersecurity risk management",
            ov_client=self.ov,
            qdrant_client=self.qdrant,
            doc_ids=[self.doc_id],
            depth="abstract",
        )
        traj = result["retrieval_trajectory"]
        self.assertGreater(
            traj["qdrant_candidates"],
            0,
            "Qdrant must have returned candidates for this doc",
        )


# ---------------------------------------------------------------------------
# TestMCPScanRegulatoryFilings
# Tests the scan_regulatory_filings MCP tool via StandaloneServer.handle_request.
# Verifies that returned filings carry correct source attribution fields.
# ---------------------------------------------------------------------------


class TestMCPScanRegulatoryFilings(unittest.TestCase):
    """MCP scan_regulatory_filings tool: response structure and source field integrity."""

    def setUp(self):
        import tempfile

        import app.naturalsentinel.mcp.server as mcp_mod
        from tests.naturalsentinel.conftest import make_memory

        self._tmp = tempfile.mkdtemp()
        mcp_mod._memory = make_memory()
        mcp_mod._runtime = None  # force re-creation with fresh memory
        from app.naturalsentinel.mcp.server import StandaloneServer

        self.server = StandaloneServer()
        # Override state_path so _scan can write without hitting working-dir
        self.server.runtime.state_path = os.path.join(self._tmp, "state.json")

    def _scan(self, domains=None, days=120):
        # Use a wide look-back window so sample-data fixtures (months old) are returned
        args = {"days": days}
        if domains:
            args["domains"] = domains
        return self.server.handle_request(
            {
                "method": "tools/call",
                "params": {"name": "scan_regulatory_filings", "arguments": args},
            }
        )

    def test_scan_returns_result_not_error(self):
        resp = self._scan()
        self.assertNotIn(
            "error",
            resp,
            f"scan_regulatory_filings returned error: {resp.get('error')}",
        )
        self.assertIn("result", resp)

    def test_scan_result_has_success_status(self):
        resp = self._scan()
        result = resp["result"]
        self.assertEqual(result.get("status"), "success")

    def test_scan_result_has_filings_analyzed_key(self):
        resp = self._scan()
        result = resp["result"]
        self.assertIn("filings_analyzed", result)
        self.assertIsInstance(result["filings_analyzed"], int)

    def test_scan_result_filings_analyzed_matches_results_length(self):
        resp = self._scan()
        result = resp["result"]
        self.assertEqual(result["filings_analyzed"], len(result.get("results", [])))

    def test_scan_results_filings_have_source_url(self):
        """Every analyzed filing must carry a non-empty source_url."""
        resp = self._scan()
        results = resp["result"].get("results", [])
        self.assertGreater(
            len(results), 0, "Expected at least one analyzed filing from sample data"
        )
        for entry in results:
            filing = entry.get("filing", {})
            source_url = filing.get("source_url", "")
            self.assertTrue(
                bool(source_url),
                f"Filing '{filing.get('title', '?')}' missing source_url in result",
            )

    def test_scan_results_filings_have_domain(self):
        """Every analyzed filing must identify its regulatory domain."""
        resp = self._scan()
        results = resp["result"].get("results", [])
        for entry in results:
            filing = entry.get("filing", {})
            self.assertTrue(
                bool(filing.get("domain")),
                f"Filing missing domain: {filing.get('title')}",
            )

    def test_scan_results_filings_have_title(self):
        """Every analyzed filing must have a non-empty title."""
        resp = self._scan()
        results = resp["result"].get("results", [])
        for entry in results:
            filing = entry.get("filing", {})
            self.assertTrue(bool(filing.get("title")), "Filing missing title")

    def test_scan_results_filings_have_id(self):
        """Every analyzed filing must have an id for deduplication."""
        resp = self._scan()
        results = resp["result"].get("results", [])
        for entry in results:
            filing = entry.get("filing", {})
            self.assertTrue(bool(filing.get("id")), "Filing missing id")

    def test_scan_domain_filter_restricts_to_requested_domain(self):
        """Passing domains=['sec'] must return only SEC filings."""
        resp = self._scan(domains=["sec"])
        results = resp["result"].get("results", [])
        if results:  # may be 0 if all SEC filings were already seen — check structure
            for entry in results:
                filing = entry.get("filing", {})
                self.assertEqual(
                    filing.get("domain"), "sec", "domain filter must restrict to 'sec'"
                )

    def test_scan_source_url_is_http_url(self):
        """source_url values must look like HTTP(S) URLs, not empty strings or placeholders."""
        resp = self._scan()
        results = resp["result"].get("results", [])
        for entry in results:
            url = entry.get("filing", {}).get("source_url", "")
            self.assertTrue(
                url.startswith("http://") or url.startswith("https://"),
                f"source_url '{url}' is not a valid HTTP URL",
            )

    def test_scan_results_include_impact_analysis(self):
        """Each result entry must contain an 'impact' block alongside 'filing'."""
        resp = self._scan()
        results = resp["result"].get("results", [])
        self.assertGreater(len(results), 0)
        for entry in results:
            self.assertIn(
                "impact", entry, "Result entry must have 'impact' alongside 'filing'"
            )


if __name__ == "__main__":
    unittest.main()
