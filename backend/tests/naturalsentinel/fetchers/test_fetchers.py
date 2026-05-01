"""Tests for naturalsentinel.fetchers — filing retrieval and sample data."""

from app.naturalsentinel.fetchers import DOMAIN_BUSINESS_LINES, fetch_filings
from app.naturalsentinel.fetchers.sample_data import SAMPLE_FILINGS
from app.naturalsentinel.models import ChangeType, RegulatoryDomain


class TestSampleData:
    def test_sample_filings_not_empty(self):
        assert len(SAMPLE_FILINGS) >= 6

    def test_sample_filings_have_recent_entries(self):
        """Fixture-rot guard (Phase P0.5).

        The ``since_days=365`` fetcher tests silently degrade if the
        whole fixture set ages out of the window. This test fails
        loudly if *no* sample entry falls within the last 400 days —
        i.e. the fixtures are so stale that the filter tests no longer
        exercise real code paths. The 400-day window gives some slack
        around the 365-day tests without demanding weekly refreshes.

        Historical anchors like ``SEC-2023-0726-CYB`` (the real SEC
        cybersecurity rule) are kept intentionally; see
        ``data/samples/__init__.py`` for the fixture policy.
        """
        from datetime import UTC, datetime, timedelta

        cutoff = datetime.now(UTC).date() - timedelta(days=400)
        recent = [
            f
            for f in SAMPLE_FILINGS
            if datetime.strptime(f["published_date"], "%Y-%m-%d").date() >= cutoff
        ]
        assert recent, (
            "Every SAMPLE_FILINGS entry is older than 400 days; the "
            "since_days=365 fetcher tests are not exercising real "
            "filter code paths. Refresh data/samples/filings.json."
        )

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
        # since_days=365 filters out any sample fixtures older than the window.
        # Assert: returned subset is non-empty and a subset of SAMPLE_FILINGS.
        results = fetch_filings(since_days=365)
        assert len(results) > 0
        assert len(results) <= len(SAMPLE_FILINGS)
        sample_ids = {f["id"] for f in SAMPLE_FILINGS}
        assert {r.id for r in results}.issubset(sample_ids)

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
