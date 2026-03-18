"""Tests for naturalsentinel.cli local document ingestion and parser behavior."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from naturalsentinel.cli import (
    _collect_input_files,
    _read_document_text,
    analyze_local_documents,
    build_local_filings,
    build_parser,
)
from naturalsentinel.models import RegulatoryDomain
from naturalsentinel.providers.mock import MockProvider


class TestCliDocumentLoading(unittest.TestCase):
    def test_read_json_document_formats_for_prompting(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notice.json"
            path.write_text('{"title": "Risk Notice", "body": "Capital impact"}')

            text = _read_document_text(path)

            self.assertIn('"title": "Risk Notice"', text)
            self.assertIn('"body": "Capital impact"', text)

    def test_collect_input_files_from_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "doc1.txt").write_text("alpha")
            (root / "doc2.md").write_text("beta")
            (root / "ignore.csv").write_text("gamma")

            files = _collect_input_files(None, str(root), recursive=False)

            self.assertEqual([p.name for p in files], ["doc1.txt", "doc2.md"])

    def test_build_local_filings_from_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "fed_margin_rule.txt"
            path.write_text("Margin and capital requirements update.")

            filings = build_local_filings([str(path)], None, RegulatoryDomain.FED)

            self.assertEqual(len(filings), 1)
            self.assertEqual(filings[0].domain, RegulatoryDomain.FED)
            self.assertTrue(filings[0].id.startswith("LOCAL-FED-0001"))
            self.assertIn("fed margin rule", filings[0].title.lower())


class TestCliLocalAnalysis(unittest.TestCase):
    def test_analyze_local_documents_returns_structured_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "custom_notice.txt"
            path.write_text("A custom local regulatory notice for testing.")

            data = analyze_local_documents(
                provider=MockProvider(),
                domain=RegulatoryDomain.SEC,
                input_paths=[str(path)],
                input_dir=None,
                state_path=str(Path(tmpdir) / "local_state.json"),
            )

            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["filing"]["domain"], "sec")
            self.assertEqual(data[0]["filing"]["source_url"], path.resolve().as_uri())
            self.assertIn("severity", data[0]["impact"])


class TestCliParser(unittest.TestCase):
    def test_parser_accepts_local_input_flags(self):
        parser = build_parser()
        args = parser.parse_args(
            ["--provider", "mock", "--input-path", "docs/example.txt", "--input-domain", "fed"]
        )

        self.assertEqual(args.provider, "mock")
        self.assertEqual(args.input_paths, ["docs/example.txt"])
        self.assertEqual(args.input_domain, "fed")


if __name__ == "__main__":
    unittest.main()
