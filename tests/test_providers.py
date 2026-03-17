"""Tests for naturalsentinel.providers — mock and provider factory."""

import json
import pytest

from naturalsentinel.providers.base import ModelProvider
from naturalsentinel.providers.mock import MockProvider
from naturalsentinel.cli import build_provider


class TestMockProvider:
    def test_implements_interface(self):
        provider = MockProvider()
        assert isinstance(provider, ModelProvider)

    def test_name(self):
        assert MockProvider().name() == "MockProvider/demo"

    def test_returns_json_for_known_filing(self):
        provider = MockProvider()
        result = provider.complete("system", "Analyze SEC-2026-0312-A filing")
        parsed = json.loads(result)
        assert parsed["severity"] == "critical"
        assert "affected_business_lines" in parsed

    def test_returns_fallback_for_unknown(self):
        provider = MockProvider()
        result = provider.complete("system", "Analyze UNKNOWN-999 filing")
        parsed = json.loads(result)
        assert parsed["severity"] == "low"
        assert parsed["confidence"] == 0.3

    def test_all_sample_filings_have_analyses(self):
        from naturalsentinel.fetchers.sample_data import SAMPLE_FILINGS, MOCK_ANALYSES
        for filing in SAMPLE_FILINGS:
            assert filing["id"] in MOCK_ANALYSES, f"Missing mock analysis for {filing['id']}"


class TestBuildProvider:
    def test_mock_provider(self):
        provider = build_provider("mock")
        assert isinstance(provider, MockProvider)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            build_provider("nonexistent_provider")

    def test_anthropic_import_error(self):
        """Anthropic provider should raise ImportError if SDK not installed."""
        # This test verifies the error handling path — the SDK may or may not be installed
        try:
            provider = build_provider("anthropic")
            # If it succeeds, that's fine (SDK is installed)
            assert provider.name().startswith("Anthropic/")
        except ImportError:
            pass  # Expected if SDK not installed
