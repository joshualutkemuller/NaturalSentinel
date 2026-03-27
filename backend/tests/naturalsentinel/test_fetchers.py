"""Tests for naturalsentinel.fetchers — filing retrieval and sample data."""

from app.naturalsentinel.fetchers import DOMAIN_BUSINESS_LINES, fetch_filings
from app.naturalsentinel.fetchers.sample_data import SAMPLE_FILINGS
from app.naturalsentinel.models import ChangeType, RegulatoryDomain


class TestSampleData:
    def test_sample_filings_not_empty(self):
        assert len(SAMPLE_FILINGS) >= 6

    def test_all_filings_have_required_fields(self):
        required = {
            "id",
            "title",
            "domain",
            "source_url",
            "published_date",
            "change_type",
            "raw_text",
        }
        for filing in SAMPLE_FILINGS:
            assert required <= set(filing.keys()), f"Missing fields in {filing['id']}"

    def test_domains_are_valid(self):
        valid = {d.value for d in RegulatoryDomain}
        for filing in SAMPLE_FILINGS:
            assert filing["domain"] in valid

    def test_change_types_are_valid(self):
        valid = {ct.value for ct in ChangeType}
        for filing in SAMPLE_FILINGS:
            assert filing["change_type"] in valid


class TestFetchFilings:
    def test_fetch_all(self):
        results = fetch_filings(since_days=365)
        assert len(results) == len(SAMPLE_FILINGS)

    def test_fetch_by_domain(self):
        sec_only = fetch_filings(domains=[RegulatoryDomain.SEC], since_days=365)
        assert all(f.domain == RegulatoryDomain.SEC for f in sec_only)
        assert len(sec_only) >= 1

    def test_fetch_multiple_domains(self):
        results = fetch_filings(
            domains=[RegulatoryDomain.SEC, RegulatoryDomain.FDA], since_days=365
        )
        domains = {f.domain for f in results}
        assert domains <= {RegulatoryDomain.SEC, RegulatoryDomain.FDA}

    def test_since_days_filtering(self):
        # Very short window should exclude older filings
        recent = fetch_filings(since_days=1)
        all_filings = fetch_filings(since_days=365)
        assert len(recent) <= len(all_filings)

    def test_filing_objects_well_formed(self):
        results = fetch_filings(since_days=365)
        for f in results:
            assert f.id
            assert f.title
            assert f.raw_text
            assert f.domain in RegulatoryDomain
            assert f.change_type in ChangeType


class TestDomainBusinessLines:
    def test_all_domains_covered(self):
        for domain in RegulatoryDomain:
            assert domain.value in DOMAIN_BUSINESS_LINES

    def test_lines_not_empty(self):
        for domain, lines in DOMAIN_BUSINESS_LINES.items():
            assert len(lines) > 0, f"No business lines for {domain}"
