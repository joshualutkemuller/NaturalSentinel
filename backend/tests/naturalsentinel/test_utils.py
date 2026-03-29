"""Tests for naturalsentinel.utils — parsing, serialization, and text helpers."""

import json

import pytest

from app.naturalsentinel.models import (
    ChangeType,
    DecisionFrame,
    ImpactAssessment,
    MonitorResult,
    RegulatoryDomain,
    RegulatoryFiling,
    Severity,
)
from app.naturalsentinel.utils.parsing import extract_json_block, parse_llm_json
from app.naturalsentinel.utils.serialization import enum_serializer, serialize_result
from app.naturalsentinel.utils.text import keyword_similarity, tokenize

# ── Text utilities ────────────────────────────────────────────────────────


class TestTokenize:
    def test_basic(self):
        assert tokenize("Hello, World!") == ["hello", "world"]

    def test_numbers(self):
        assert tokenize("PM2.5 standard 8.0 µg/m³") == [
            "pm2",
            "5",
            "standard",
            "8",
            "0",
            "g",
            "m",
        ]

    def test_empty(self):
        assert tokenize("") == []
        assert tokenize("!!!") == []


class TestKeywordSimilarity:
    def test_identical(self):
        tokens = ["climate", "disclosure", "sec"]
        assert keyword_similarity(tokens, tokens) == 1.0

    def test_no_overlap(self):
        assert keyword_similarity(["apple", "banana"], ["car", "dog"]) == 0.0

    def test_partial_overlap(self):
        score = keyword_similarity(["climate", "sec"], ["climate", "fda"])
        assert 0.0 < score < 1.0

    def test_empty_inputs(self):
        assert keyword_similarity([], ["word"]) == 0.0
        assert keyword_similarity(["word"], []) == 0.0


# ── JSON parsing ──────────────────────────────────────────────────────────


class TestExtractJsonBlock:
    def test_clean_json(self):
        raw = '{"key": "value"}'
        assert extract_json_block(raw) == raw

    def test_markdown_fences(self):
        raw = '```json\n{"key": "value"}\n```'
        result = extract_json_block(raw)
        assert json.loads(result) == {"key": "value"}

    def test_fences_no_lang(self):
        raw = '```\n{"severity": "high"}\n```'
        result = extract_json_block(raw)
        assert json.loads(result)["severity"] == "high"

    def test_preamble_text(self):
        raw = 'Here is the analysis:\n\n{"severity": "critical"}'
        result = extract_json_block(raw)
        assert json.loads(result)["severity"] == "critical"


class TestParseLlmJson:
    def test_valid_json(self):
        result = parse_llm_json('{"severity": "high", "confidence": 0.9}')
        assert result["severity"] == "high"

    def test_with_fences(self):
        result = parse_llm_json('```json\n{"severity": "low"}\n```')
        assert result["severity"] == "low"

    def test_fallback_on_bad_json(self):
        fallback = {"severity": "medium", "confidence": 0.3}
        result = parse_llm_json("This is not JSON at all.", fallback=fallback)
        assert result == fallback

    def test_raises_without_fallback(self):
        with pytest.raises(ValueError, match="unparseable"):
            parse_llm_json("Not JSON")


# ── Serialization ─────────────────────────────────────────────────────────


class TestEnumSerializer:
    def test_enum_value(self):
        assert enum_serializer(Severity.HIGH) == "high"
        assert enum_serializer(RegulatoryDomain.SEC) == "sec"

    def test_non_enum_str(self):
        from datetime import datetime

        result = enum_serializer(datetime(2026, 1, 1))
        assert "2026" in result


class TestSerializeResult:
    def test_roundtrip(self):
        filing = RegulatoryFiling(
            id="T-001",
            title="Test",
            domain=RegulatoryDomain.SEC,
            source_url="https://x.com",
            published_date="2026-01-01",
            raw_text="text",
            change_type=ChangeType.FINAL_RULE,
        )
        impact = ImpactAssessment(
            filing_id="T-001",
            severity=Severity.CRITICAL,
            affected_business_lines=["Equities"],
            affected_regulations=["Reg S-K"],
            compliance_deadline="2026-12-15",
            action_items=["Do something"],
            risk_summary="Big risk",
            confidence=0.95,
        )
        decision = DecisionFrame(
            decision_id="decision::T-001",
            question="What response is warranted?",
            scope="SEC filing review",
            time_horizon="near-term",
        )
        result = MonitorResult(
            filing=filing, impact=impact, decision=decision, raw_analysis="{}"
        )
        serialized = serialize_result(result)

        # All enum values should be plain strings
        assert serialized["filing"]["domain"] == "sec"
        assert serialized["filing"]["change_type"] == "final_rule"
        assert serialized["impact"]["severity"] == "critical"

        # Should be valid JSON
        json.dumps(serialized)  # no raise
