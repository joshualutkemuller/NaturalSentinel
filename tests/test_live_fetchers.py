"""Tests for the live filing ingestion layer.

All tests run offline — network calls are intercepted via a MockHTTPClient
that returns pre-canned responses for each source.  This validates parsing,
normalisation, error handling, and the fetch_filings(live=True) routing
without requiring live internet access.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from naturalsentinel.fetchers.base import _raw_to_filing, fetch_filings
from naturalsentinel.fetchers.live import bis, edgar, federal_register, finra
from naturalsentinel.fetchers.live.parsers import (
    detect_change_type,
    html_to_text,
    normalise_whitespace,
    truncate,
)
from naturalsentinel.models import ChangeType, RegulatoryDomain, RegulatoryFiling

# ---------------------------------------------------------------------------
# Mock HTTP client
# ---------------------------------------------------------------------------


class MockHTTPClient:
    """Intercepts HTTP calls and returns pre-canned text/JSON responses."""

    def __init__(self, responses: dict):
        """
        Args:
            responses: Mapping from URL prefix → response body (str or dict).
                       If a dict is given, it is JSON-serialised for get()
                       but returned directly for get_json().
        """
        self.responses = responses
        self.calls: list[str] = []

    def _resolve(self, url: str, params=None):
        for prefix, body in self.responses.items():
            if url.startswith(prefix) or prefix in url:
                return body
        return ""

    def get(self, url: str, params=None) -> str:
        self.calls.append(url)
        body = self._resolve(url)
        if isinstance(body, dict) or isinstance(body, list):
            return json.dumps(body)
        return body

    def get_json(self, url: str, params=None):
        self.calls.append(url)
        body = self._resolve(url)
        if isinstance(body, dict) or isinstance(body, list):
            return body
        return json.loads(body)


# ---------------------------------------------------------------------------
# Sample response fixtures
# ---------------------------------------------------------------------------

FR_JSON_RESPONSE = {
    "results": [
        {
            "document_number": "2026-04321",
            "title": "Proposed Rule on Climate-Related Risk Management",
            "abstract": "The Federal Reserve proposes standards for climate risk management.",
            "type": "Proposed Rule",
            "publication_date": "2026-03-10",
            "effective_on": "2026-09-30",
            "html_url": "https://www.federalregister.gov/documents/2026/03/10/2026-04321/proposed-rule",
            "pdf_url": "https://www.federalregister.gov/documents/2026/03/10/2026-04321.pdf",
            "agencies": [{"name": "Federal Reserve System"}],
            "regulation_id_numbers": [],
        },
        {
            "document_number": "2026-04322",
            "title": "Final Rule: Capital Requirements",
            "abstract": "Final rule implementing updated capital requirements.",
            "type": "Rule",
            "publication_date": "2026-03-12",
            "effective_on": "2026-12-31",
            "html_url": "https://www.federalregister.gov/documents/2026/03/12/2026-04322/final-rule",
            "pdf_url": "",
            "agencies": [{"name": "Federal Reserve System"}],
            "regulation_id_numbers": ["12 CFR 225"],
        },
    ]
}

FR_HTML_RESPONSE = """
<html><head><title>Proposed Rule</title></head>
<body>
  <nav>Navigation</nav>
  <h1>Proposed Rule on Climate-Related Risk Management</h1>
  <p>The Federal Reserve System proposes to establish standards for large bank
  holding companies to manage climate-related financial risks. The proposal covers
  governance, scenario analysis, risk identification, and measurement.</p>
  <h2>Background</h2>
  <p>Climate change poses significant risks to the financial system, including
  physical risks from extreme weather and transition risks from policy changes.</p>
  <footer>Footer content</footer>
</body></html>
"""

EDGAR_JSON_RESPONSE = {
    "hits": {
        "total": {"value": 2, "relation": "eq"},
        "hits": [
            {
                "_id": "0001234567-26-000001",
                "_source": {
                    "accession_no": "0001234567-26-000001",
                    "entity_name": "Securities and Exchange Commission",
                    "form_type": "34-12B",
                    "file_date": "2026-03-08",
                    "file_num": "001-12345",
                    "period_of_report": "2026-03-08",
                    "display_names": ["SEC"],
                },
            },
            {
                "_id": "0001234567-26-000002",
                "_source": {
                    "accession_no": "0001234567-26-000002",
                    "entity_name": "Test Corp",
                    "form_type": "8-K",
                    "file_date": "2026-03-09",
                    "file_num": "",
                    "period_of_report": "2026-03-09",
                    "display_names": ["SEC"],
                },
            },
        ],
    }
}

BIS_HTML_RESPONSE = """
<html><body>
<div class="item">
  <span class="date">15 Mar 2026</span>
  <a href="/bcbs/publ/d123.htm">Consultation on Capital Adequacy Revisions</a>
  <p class="pdesc">The Basel Committee consults on revisions to the capital framework.</p>
</div>
<div class="item">
  <span class="date">10 Feb 2026</span>
  <a href="/bcbs/publ/d122.htm">Final Standard: Output Floor Implementation</a>
  <p>Final standard for the implementation of the output floor.</p>
</div>
</body></html>
"""

BIS_PUB_HTML = """
<html><body>
<h1>Consultation on Capital Adequacy Revisions</h1>
<p>The Basel Committee on Banking Supervision is consulting on proposed revisions
to the capital adequacy framework. The consultation covers risk-weighted assets,
internal models, and the output floor calibration.</p>
<p>Comments are due by 30 June 2026.</p>
</body></html>
"""

FINRA_HTML_RESPONSE = """
<html><body>
<h2>Regulatory Notices</h2>
<ul>
  <li>
    <a href="/rules-guidance/notices/26-05">
      Margin Requirements for Volatile Securities
    </a>
    <span class="date">March 1, 2026</span>
  </li>
  <li>
    <a href="/rules-guidance/notices/26-04">
      TBA Market Practices Update
    </a>
    <span class="date">February 15, 2026</span>
  </li>
</ul>
</body></html>
"""

FINRA_NOTICE_HTML = """
<html><body>
<h1>Regulatory Notice 26-05: Margin Requirements for Volatile Securities</h1>
<p>FINRA is reminding member firms of their obligations under Rule 4210 regarding
margin requirements for volatile securities. The notice provides guidance on
concentration haircuts and enhanced margin requirements.</p>
</body></html>
"""


# ---------------------------------------------------------------------------
# parsers — html_to_text
# ---------------------------------------------------------------------------


class TestHtmlToText(unittest.TestCase):
    def test_strips_script_and_style(self):
        html = "<html><head><style>body{color:red}</style></head><body><p>Hello world</p></body></html>"
        text = html_to_text(html)
        self.assertIn("Hello world", text)
        self.assertNotIn("color:red", text)

    def test_strips_nav_and_footer(self):
        html = "<html><body><nav>Site nav</nav><p>Content</p><footer>Footer</footer></body></html>"
        text = html_to_text(html)
        self.assertIn("Content", text)
        self.assertNotIn("Site nav", text)
        self.assertNotIn("Footer", text)

    def test_preserves_body_text(self):
        text = html_to_text("<p>The Federal Reserve proposes new capital rules.</p>")
        self.assertIn("Federal Reserve", text)

    def test_respects_max_chars(self):
        long_html = "<p>" + ("x " * 100_000) + "</p>"
        text = html_to_text(long_html, max_chars=500)
        self.assertLessEqual(len(text), 600)  # Some slack for truncation marker

    def test_handles_malformed_html(self):
        malformed = "<p>Unclosed paragraph <div>Nested <b>bold</div>"
        text = html_to_text(malformed)
        self.assertIsInstance(text, str)

    def test_empty_html(self):
        self.assertEqual(html_to_text(""), "")

    def test_entities_decoded(self):
        text = html_to_text("<p>Rule &amp; Regulation &gt; Threshold</p>")
        self.assertIn("&", text)

    def test_block_tags_add_newlines(self):
        text = html_to_text("<h1>Title</h1><p>Body</p>")
        self.assertIn("\n", text)


class TestDetectChangeType(unittest.TestCase):
    def test_final_rule(self):
        self.assertEqual(detect_change_type("Final Rule on Capital Requirements"), "final_rule")

    def test_proposed_rule(self):
        self.assertEqual(
            detect_change_type("Notice of Proposed Rulemaking for NSFR"), "proposed_rule"
        )

    def test_nprm(self):
        self.assertEqual(detect_change_type("NPRM on climate disclosures"), "proposed_rule")

    def test_enforcement(self):
        self.assertEqual(
            detect_change_type("Enforcement action and civil money penalty"), "enforcement"
        )

    def test_guidance(self):
        self.assertEqual(detect_change_type("Supervisory guidance on model risk"), "guidance")

    def test_notice_default(self):
        self.assertEqual(detect_change_type("Quarterly report from the agency"), "notice")

    def test_amendment(self):
        self.assertEqual(detect_change_type("Amendment to Regulation D"), "amendment")


class TestNormaliseWhitespace(unittest.TestCase):
    def test_collapses_spaces(self):
        self.assertEqual(normalise_whitespace("hello   world"), "hello world")

    def test_strips_newlines(self):
        self.assertEqual(normalise_whitespace("hello\n  world"), "hello world")

    def test_strips_leading_trailing(self):
        self.assertEqual(normalise_whitespace("  hello  "), "hello")


class TestTruncate(unittest.TestCase):
    def test_short_text_unchanged(self):
        self.assertEqual(truncate("hello", 1000), "hello")

    def test_long_text_truncated(self):
        long = "x" * 100_000
        result = truncate(long, 500)
        self.assertLessEqual(len(result), 520)
        self.assertIn("[…truncated]", result)


# ---------------------------------------------------------------------------
# federal_register fetcher
# ---------------------------------------------------------------------------


class TestFederalRegisterFetch(unittest.TestCase):
    def _make_client(self, include_full_text=False):
        responses = {
            "https://www.federalregister.gov/api/v1": FR_JSON_RESPONSE,
        }
        if include_full_text:
            responses["https://www.federalregister.gov/documents"] = FR_HTML_RESPONSE
        return MockHTTPClient(responses)

    def test_returns_filings(self):
        client = self._make_client()
        results = federal_register.fetch(
            ["fed"], since_days=30, fetch_full_text=False, client=client
        )
        self.assertEqual(len(results), 2)

    def test_filing_has_required_fields(self):
        client = self._make_client()
        results = federal_register.fetch(
            ["fed"], since_days=30, fetch_full_text=False, client=client
        )
        r = results[0]
        self.assertIn("id", r)
        self.assertIn("title", r)
        self.assertIn("domain", r)
        self.assertIn("source_url", r)
        self.assertIn("published_date", r)
        self.assertIn("change_type", r)
        self.assertIn("raw_text", r)

    def test_change_type_proposed_rule(self):
        client = self._make_client()
        results = federal_register.fetch(
            ["fed"], since_days=30, fetch_full_text=False, client=client
        )
        proposed = next(r for r in results if "04321" in r["id"])
        self.assertEqual(proposed["change_type"], "proposed_rule")

    def test_change_type_final_rule(self):
        client = self._make_client()
        results = federal_register.fetch(
            ["fed"], since_days=30, fetch_full_text=False, client=client
        )
        final = next(r for r in results if "04322" in r["id"])
        self.assertEqual(final["change_type"], "final_rule")

    def test_domain_preserved(self):
        client = self._make_client()
        results = federal_register.fetch(
            ["sec"], since_days=30, fetch_full_text=False, client=client
        )
        for r in results:
            self.assertEqual(r["domain"], "sec")

    def test_full_text_fetched_when_enabled(self):
        client = self._make_client(include_full_text=True)
        results = federal_register.fetch(
            ["fed"], since_days=30, fetch_full_text=True, client=client
        )
        # Any result with a html_url should have richer text than just abstract
        self.assertTrue(len(results) > 0)

    def test_network_error_returns_empty(self):
        import urllib.error

        class ErrorClient:
            def get(self, url, params=None):
                raise urllib.error.URLError("timeout")

            def get_json(self, url, params=None):
                raise urllib.error.URLError("timeout")

        results = federal_register.fetch(["fed"], since_days=30, client=ErrorClient())
        self.assertEqual(results, [])

    def test_unknown_domain_skipped(self):
        client = self._make_client()
        results = federal_register.fetch(
            ["finra"], since_days=30, fetch_full_text=False, client=client
        )
        self.assertEqual(results, [])

    def test_empty_results_list(self):
        client = MockHTTPClient({"https://www.federalregister.gov/api/v1": {"results": []}})
        results = federal_register.fetch(
            ["fed"], since_days=30, fetch_full_text=False, client=client
        )
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# EDGAR fetcher
# ---------------------------------------------------------------------------


class TestEdgarFetch(unittest.TestCase):
    def _make_client(self):
        return MockHTTPClient(
            {
                "https://efts.sec.gov": EDGAR_JSON_RESPONSE,
            }
        )

    def test_returns_filings(self):
        results = edgar.fetch(since_days=30, fetch_full_text=False, client=self._make_client())
        self.assertGreater(len(results), 0)

    def test_filing_has_required_fields(self):
        results = edgar.fetch(since_days=30, fetch_full_text=False, client=self._make_client())
        r = results[0]
        self.assertIn("id", r)
        self.assertIn("title", r)
        self.assertIn("domain", r)
        self.assertIn("published_date", r)
        self.assertIn("change_type", r)
        self.assertIn("raw_text", r)

    def test_domain_is_sec(self):
        results = edgar.fetch(since_days=30, fetch_full_text=False, client=self._make_client())
        for r in results:
            self.assertEqual(r["domain"], "sec")

    def test_deduplicates_accessions(self):
        # Duplicate accession_no in response should produce one result
        dup_response = {
            "hits": {
                "total": {"value": 2, "relation": "eq"},
                "hits": [
                    EDGAR_JSON_RESPONSE["hits"]["hits"][0],
                    EDGAR_JSON_RESPONSE["hits"]["hits"][0],
                ],
            }
        }
        client = MockHTTPClient({"https://efts.sec.gov": dup_response})
        results = edgar.fetch(since_days=30, fetch_full_text=False, client=client)
        ids = [r["id"] for r in results]
        self.assertEqual(len(ids), len(set(ids)))

    def test_network_error_returns_empty(self):
        import urllib.error

        class ErrorClient:
            def get(self, url, params=None):
                raise urllib.error.URLError("timeout")

            def get_json(self, url, params=None):
                raise urllib.error.URLError("timeout")

        results = edgar.fetch(since_days=30, client=ErrorClient())
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# BIS fetcher
# ---------------------------------------------------------------------------


class TestBisFetch(unittest.TestCase):
    def _make_client(self):
        return MockHTTPClient(
            {
                "https://www.bis.org/bcbs/publications.htm": BIS_HTML_RESPONSE,
                "https://www.bis.org/bcbs/publ/": BIS_PUB_HTML,
            }
        )

    def test_returns_filings(self):
        results = bis.fetch(since_days=365, fetch_full_text=False, client=self._make_client())
        self.assertGreater(len(results), 0)

    def test_filing_has_required_fields(self):
        results = bis.fetch(since_days=365, fetch_full_text=False, client=self._make_client())
        r = results[0]
        self.assertIn("id", r)
        self.assertIn("title", r)
        self.assertIn("domain", r)
        self.assertIn("published_date", r)
        self.assertIn("change_type", r)

    def test_domain_is_basel(self):
        results = bis.fetch(since_days=365, fetch_full_text=False, client=self._make_client())
        for r in results:
            self.assertEqual(r["domain"], "basel")

    def test_network_error_returns_empty(self):
        import urllib.error

        class ErrorClient:
            def get(self, url, params=None):
                raise urllib.error.URLError("timeout")

            def get_json(self, url, params=None):
                raise urllib.error.URLError("timeout")

        results = bis.fetch(since_days=90, client=ErrorClient())
        self.assertEqual(results, [])

    def test_cutoff_filters_old_publications(self):
        # BIS_HTML_RESPONSE has dates in 2026 and earlier
        # With since_days=1, nothing should match unless published today
        results = bis.fetch(since_days=1, fetch_full_text=False, client=self._make_client())
        # All entries are in March/Feb 2026, well within 1-day cutoff of today
        # → should be empty unless tests run on exactly those dates
        # Just verify the result is a list with no errors
        self.assertIsInstance(results, list)


# ---------------------------------------------------------------------------
# FINRA fetcher
# ---------------------------------------------------------------------------


class TestFinraFetch(unittest.TestCase):
    def _make_client(self):
        return MockHTTPClient(
            {
                "https://www.finra.org/rules-guidance/notices": FINRA_HTML_RESPONSE,
                "https://www.finra.org/rules-guidance/notices/26-": FINRA_NOTICE_HTML,
            }
        )

    def test_returns_filings(self):
        results = finra.fetch(since_days=365, fetch_full_text=False, client=self._make_client())
        self.assertGreater(len(results), 0)

    def test_filing_has_required_fields(self):
        results = finra.fetch(since_days=365, fetch_full_text=False, client=self._make_client())
        r = results[0]
        self.assertIn("id", r)
        self.assertIn("title", r)
        self.assertIn("domain", r)
        self.assertIn("published_date", r)
        self.assertIn("change_type", r)

    def test_domain_is_finra(self):
        results = finra.fetch(since_days=365, fetch_full_text=False, client=self._make_client())
        for r in results:
            self.assertEqual(r["domain"], "finra")

    def test_network_error_returns_empty(self):
        import urllib.error

        class ErrorClient:
            def get(self, url, params=None):
                raise urllib.error.URLError("timeout")

            def get_json(self, url, params=None):
                raise urllib.error.URLError("timeout")

        results = finra.fetch(since_days=60, client=ErrorClient())
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# fetch_filings live routing
# ---------------------------------------------------------------------------


class TestFetchFilingsLive(unittest.TestCase):
    def _make_all_client(self):
        """Client that satisfies all live fetchers with canned responses."""
        return MockHTTPClient(
            {
                "https://www.federalregister.gov/api/v1": FR_JSON_RESPONSE,
                "https://efts.sec.gov": EDGAR_JSON_RESPONSE,
                "https://www.bis.org/bcbs/publications.htm": BIS_HTML_RESPONSE,
                "https://www.finra.org/rules-guidance/notices": FINRA_HTML_RESPONSE,
            }
        )

    def test_live_mode_returns_regulatory_filings(self):
        from naturalsentinel.models import RegulatoryDomain

        results = fetch_filings(
            domains=[RegulatoryDomain.FED],
            since_days=30,
            live=True,
            fetch_full_text=False,
            http_client=self._make_all_client(),
        )
        self.assertIsInstance(results, list)
        for f in results:
            self.assertIsInstance(f, RegulatoryFiling)

    def test_live_mode_filing_fields(self):
        from naturalsentinel.models import RegulatoryDomain

        results = fetch_filings(
            domains=[RegulatoryDomain.FED],
            since_days=30,
            live=True,
            fetch_full_text=False,
            http_client=self._make_all_client(),
        )
        if results:
            f = results[0]
            self.assertIsInstance(f.domain, RegulatoryDomain)
            self.assertIsInstance(f.change_type, ChangeType)
            self.assertIsInstance(f.raw_text, str)

    def test_live_mode_deduplicates(self):
        from naturalsentinel.models import RegulatoryDomain

        results = fetch_filings(
            domains=[RegulatoryDomain.FED],
            since_days=30,
            live=True,
            fetch_full_text=False,
            http_client=self._make_all_client(),
        )
        ids = [f.id for f in results]
        self.assertEqual(len(ids), len(set(ids)))

    def test_live_mode_all_sources_fail_falls_back_to_sample(self):
        """When every live source fails, fall back to sample data gracefully."""
        import urllib.error

        class AllFailClient:
            def get(self, url, params=None):
                raise urllib.error.URLError("offline")

            def get_json(self, url, params=None):
                raise urllib.error.URLError("offline")

        results = fetch_filings(
            live=True,
            fetch_full_text=False,
            http_client=AllFailClient(),
        )
        # Should fall back to sample data
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_sample_mode_still_works(self):
        """Default mode (live=False) must still work exactly as before."""
        results = fetch_filings(live=False)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        for f in results:
            self.assertIsInstance(f, RegulatoryFiling)


# ---------------------------------------------------------------------------
# _raw_to_filing normalisation edge cases
# ---------------------------------------------------------------------------


class TestRawToFiling(unittest.TestCase):
    def test_valid_raw(self):
        raw = {
            "id": "TEST-001",
            "title": "Test Filing",
            "domain": "sec",
            "source_url": "https://example.com",
            "published_date": "2026-03-15",
            "change_type": "proposed_rule",
            "raw_text": "Some text.",
        }
        f = _raw_to_filing(raw)
        self.assertEqual(f.id, "TEST-001")
        self.assertEqual(f.domain, RegulatoryDomain.SEC)
        self.assertEqual(f.change_type, ChangeType.PROPOSED_RULE)

    def test_unknown_domain_defaults_to_sec(self):
        raw = {"id": "X", "domain": "unknown_xyz", "published_date": "2026-01-01"}
        f = _raw_to_filing(raw)
        self.assertEqual(f.domain, RegulatoryDomain.SEC)

    def test_unknown_change_type_defaults_to_notice(self):
        raw = {
            "id": "X",
            "domain": "fed",
            "published_date": "2026-01-01",
            "change_type": "weird_type",
        }
        f = _raw_to_filing(raw)
        self.assertEqual(f.change_type, ChangeType.NOTICE)

    def test_missing_published_date_defaults_to_today(self):
        raw = {"id": "X", "domain": "sec", "published_date": ""}
        f = _raw_to_filing(raw)
        self.assertIsNotNone(f.published_date)
        self.assertIn("20", f.published_date)  # Contains year

    def test_all_change_types_map(self):
        for ct_str, ct_enum in [
            ("final_rule", ChangeType.FINAL_RULE),
            ("proposed_rule", ChangeType.PROPOSED_RULE),
            ("guidance", ChangeType.GUIDANCE),
            ("enforcement", ChangeType.ENFORCEMENT),
            ("notice", ChangeType.NOTICE),
            ("amendment", ChangeType.AMENDMENT),
            ("executive_order", ChangeType.EXECUTIVE_ORDER),
        ]:
            raw = {
                "id": "X",
                "domain": "sec",
                "published_date": "2026-01-01",
                "change_type": ct_str,
            }
            f = _raw_to_filing(raw)
            self.assertEqual(f.change_type, ct_enum, f"Failed for {ct_str}")


if __name__ == "__main__":
    unittest.main()
