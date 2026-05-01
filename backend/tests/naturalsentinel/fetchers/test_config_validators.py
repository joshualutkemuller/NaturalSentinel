"""Tests for fetchers.config_validators.

The validator is the boot-time safety net for the five mapping dicts
that drive fetcher dispatch and filtering. These tests cover:

- Happy path: the real mappings validate cleanly (regression guard
  against a typo landing in any mapping).
- Synthetic failure: monkey-patched bad mappings raise
  ConfigurationError with a useful message listing every gap.
"""

from __future__ import annotations

import pytest

from app.naturalsentinel.fetchers.config_validators import (
    ConfigurationError,
    validate_mappings,
)


class TestValidateMappingsHappyPath:
    def test_real_mappings_validate(self):
        """Regression: the shipped mappings cover every enum value."""
        validate_mappings()


class TestValidateMappingsFailures:
    def test_invalid_domain_key_in_business_lines(self, monkeypatch):
        """A typo in DOMAIN_BUSINESS_LINES fails loudly."""
        import app.naturalsentinel.fetchers.base as base

        bad = dict(base.DOMAIN_BUSINESS_LINES)
        bad["sfdc"] = ["made up"]
        monkeypatch.setattr(base, "DOMAIN_BUSINESS_LINES", bad)

        with pytest.raises(ConfigurationError, match="DOMAIN_BUSINESS_LINES"):
            validate_mappings()

    def test_missing_sector_in_state_agencies(self, monkeypatch):
        """Dropping a sector from SECTOR_STATE_AGENCIES fails loudly."""
        import app.naturalsentinel.fetchers.state_domains as sd

        bad = {
            k: v
            for k, v in sd.SECTOR_STATE_AGENCIES.items()
            if k != "financial_services"
        }
        monkeypatch.setattr(sd, "SECTOR_STATE_AGENCIES", bad)

        with pytest.raises(ConfigurationError, match="SECTOR_STATE_AGENCIES"):
            validate_mappings()

    def test_invalid_domain_target_in_sector_mapping(self, monkeypatch):
        """A typo in a SECTOR_TO_FEDERAL_DOMAINS value fails loudly."""
        import app.naturalsentinel.fetchers.state_domains as sd

        bad = {k: list(v) for k, v in sd.SECTOR_TO_FEDERAL_DOMAINS.items()}
        bad["financial_services"].append("sfdc")
        monkeypatch.setattr(sd, "SECTOR_TO_FEDERAL_DOMAINS", bad)

        with pytest.raises(ConfigurationError, match="SECTOR_TO_FEDERAL_DOMAINS"):
            validate_mappings()

    def test_invalid_state_code_in_rss_feeds(self, monkeypatch):
        """A bad state key in STATE_AGENCY_RSS_FEEDS fails loudly."""
        import app.naturalsentinel.fetchers.state_domains as sd

        bad = dict(sd.STATE_AGENCY_RSS_FEEDS)
        bad["ZZ"] = [{"url": "x", "sector": "financial_services", "agency": "Fake"}]
        monkeypatch.setattr(sd, "STATE_AGENCY_RSS_FEEDS", bad)

        with pytest.raises(ConfigurationError, match="STATE_AGENCY_RSS_FEEDS"):
            validate_mappings()

    def test_invalid_sector_in_rss_feed_entry(self, monkeypatch):
        """A bad sector inside a feed entry fails loudly."""
        import app.naturalsentinel.fetchers.state_domains as sd

        bad = {k: [dict(f) for f in v] for k, v in sd.STATE_AGENCY_RSS_FEEDS.items()}
        bad["CA"][0]["sector"] = "crypto_things"
        monkeypatch.setattr(sd, "STATE_AGENCY_RSS_FEEDS", bad)

        with pytest.raises(ConfigurationError, match="invalid IndustrySector"):
            validate_mappings()

    def test_multiple_gaps_reported_together(self, monkeypatch):
        """When several gaps exist the error message lists every one."""
        import app.naturalsentinel.fetchers.base as base
        import app.naturalsentinel.fetchers.state_domains as sd

        bad_dbl = dict(base.DOMAIN_BUSINESS_LINES)
        bad_dbl["sfdc"] = ["made up"]
        monkeypatch.setattr(base, "DOMAIN_BUSINESS_LINES", bad_dbl)

        bad_sars = dict(sd.STATE_AGENCY_RSS_FEEDS)
        bad_sars["ZZ"] = [{"url": "x", "sector": "financial_services", "agency": "F"}]
        monkeypatch.setattr(sd, "STATE_AGENCY_RSS_FEEDS", bad_sars)

        with pytest.raises(ConfigurationError) as exc_info:
            validate_mappings()
        msg = str(exc_info.value)
        assert "DOMAIN_BUSINESS_LINES" in msg
        assert "STATE_AGENCY_RSS_FEEDS" in msg
