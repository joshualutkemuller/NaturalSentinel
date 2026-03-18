"""Tests for the styled NaturalSentinel LangChain chat shell helpers."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from naturalsentinel.langchain_chat import (
    ChatState,
    build_header_lines,
    build_parser,
    fallback_answer,
    handle_command,
    render_command_table,
)


class TestLangChainChatHelpers(unittest.TestCase):
    def test_build_header_lines(self):
        lines = build_header_lines("mock", "default")
        self.assertEqual(len(lines), 2)
        self.assertIn("NaturalSentinel", lines[0])
        self.assertIn("Provider: mock", lines[1])

    def test_render_command_table_contains_attach(self):
        table = render_command_table()
        self.assertIn("/attach <path>", table)
        self.assertIn("/exit", table)

    def test_attach_and_clear_commands(self):
        state = ChatState()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.txt"
            path.write_text("sample")

            attached = handle_command(state, f"/attach {path}")
            self.assertIn("Attached:", attached)
            self.assertEqual(len(state.attached_paths), 1)

            cleared = handle_command(state, "/clear")
            self.assertIn("cleared", cleared.lower())
            self.assertEqual(state.attached_paths, [])
            self.assertEqual(state.history, [])

    def test_fallback_answer_mentions_analysis_when_present(self):
        answer = fallback_answer(
            "What changed?",
            [
                {
                    "filing": {"title": "Local Notice"},
                    "impact": {"severity": "high", "risk_summary": "Capital impact detected"},
                }
            ],
        )
        self.assertIn("Local Notice", answer)
        self.assertIn("severity=high", answer)

    def test_parser_accepts_session_flags(self):
        parser = build_parser()
        args = parser.parse_args(["--provider", "mock", "--domain", "fed", "--session", "desk-a"])
        self.assertEqual(args.provider, "mock")
        self.assertEqual(args.domain, "fed")
        self.assertEqual(args.session, "desk-a")


if __name__ == "__main__":
    unittest.main()
