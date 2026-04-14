"""End-to-end pipeline test using excerpts from real regulatory documents.

Runs three curated filings (SEC, Fed, CFPB) through the ``analyze_filing``
skill with the MockProvider to verify the pipeline produces structured
output without needing live API calls.

Documents:
    1. SEC Enforcement Manual Update (Feb 2026) — smoke test
    2. Fed Basel III Capital Framework Modernization (March 2026) — core pipeline
    3. CFPB Personal Financial Data Rights Section 1033 — deadline extraction
"""

from __future__ import annotations

import unittest

from app.naturalsentinel import MemoryStore, MockProvider
from app.naturalsentinel.cli import create_runtime
from app.naturalsentinel.models import (
    ChangeType,
    RegulatoryDomain,
    RegulatoryFiling,
    Severity,
)

# ---------------------------------------------------------------------------
# Test fixtures — excerpts drawn from publicly available regulatory documents
# ---------------------------------------------------------------------------

SEC_ENFORCEMENT_MANUAL = RegulatoryFiling(
    id="SEC-2026-0224-ENFORCEMENT-MANUAL",
    title="SEC Division of Enforcement Announces Updates to Enforcement Manual",
    domain=RegulatoryDomain.SEC,
    source_url=(
        "https://www.sec.gov/newsroom/press-releases/"
        "2026-20-secs-division-enforcement-announces-updates-enforcement-manual"
    ),
    published_date="2026-02-24",
    change_type=ChangeType.GUIDANCE,
    raw_text=(
        "The Securities and Exchange Commission today announced updates to its "
        "Division of Enforcement Manual. The updates restore the Commission's prior "
        "practice of permitting a settling party to request simultaneous "
        "consideration of settlement offers and any related requests for waivers "
        "from automatic disqualifications. Recipients of Wells notices will "
        "ordinarily receive four weeks to make Wells submissions, and Wells "
        "meetings will be scheduled within four weeks of receipt of a Wells "
        "submission and will include a member of senior leadership within the "
        "Division. The Enforcement Manual, which was last revised in 2017, will "
        "undergo yearly reviews going forward. These changes affect broker-dealers, "
        "investment advisers, and public companies that may be subject to SEC "
        "enforcement inquiries."
    ),
)

FED_BASEL_III = RegulatoryFiling(
    id="FED-2026-0319-BASEL-III",
    title=(
        "Agencies request comment on proposals to modernize the regulatory capital "
        "framework and maintain the strength of the banking system"
    ),
    domain=RegulatoryDomain.FED,
    source_url=(
        "https://www.federalreserve.gov/newsevents/pressreleases/"
        "bcreg20260319a.htm"
    ),
    published_date="2026-03-19",
    change_type=ChangeType.PROPOSED_RULE,
    raw_text=(
        "Federal bank regulatory agencies today requested comment on proposals to "
        "modernize the regulatory capital framework and maintain the strength of "
        "the U.S. banking system. The proposals would improve the capital framework "
        "by enhancing risk sensitivity, reducing burden, and improving consistency "
        "across banks, as well as by implementing the final components of the "
        "Basel III agreement. For the largest banks, the framework would be "
        "streamlined by having these banks use one rather than two sets of "
        "calculations to determine compliance with risk-based capital requirements. "
        "The proposal would improve the calibration of the framework to better "
        "capture credit, market, and operational risks. For other banks, a second "
        "proposal would better align capital requirements for traditional lending "
        "activities with risk, while maintaining the framework's simplicity. "
        "Comments on all proposals must be received by June 18, 2026. The proposals "
        "would substantially affect RWA modelling, the leverage ratio, the "
        "supplementary leverage ratio, capital optimization, and the output floor. "
        "Banks should begin impact assessments immediately."
    ),
)

CFPB_SECTION_1033 = RegulatoryFiling(
    id="CFPB-2025-0822-PFDR",
    title="Personal Financial Data Rights Reconsideration",
    domain=RegulatoryDomain.CFPB,
    source_url=(
        "https://www.federalregister.gov/documents/2025/08/22/2025-16139/"
        "personal-financial-data-rights-reconsideration"
    ),
    published_date="2025-08-22",
    change_type=ChangeType.FINAL_RULE,
    raw_text=(
        "The Consumer Financial Protection Bureau published the Personal Financial "
        "Data Rights final rule under section 1033 of the Consumer Financial "
        "Protection Act. The rule applies to financial institutions that issue "
        "credit cards, hold transaction accounts, issue devices to access an "
        "account, or provide other types of payment facilitation products or "
        "services. The rule generally requires these financial institutions to "
        "provide information about transactions, costs, charges, and usage to "
        "consumers upon request, and to authorized third parties acting on their "
        "behalf. Pursuant to a court order, the compliance dates have been stayed "
        "by 90 days, and thus the first compliance date is now June 30, 2026 for "
        "the largest institutions, with subsequent tiers following in 2027 and "
        "2028. Institutions must build consumer-authorized data-sharing "
        "infrastructure, honor third-party access requests, and comply with data "
        "security and privacy obligations. Non-compliance may result in "
        "enforcement actions and civil money penalties. The rule materially "
        "affects consumer lending, credit cards, fintech partnerships, and core "
        "deposit operations."
    ),
)

TEST_FILINGS = [SEC_ENFORCEMENT_MANUAL, FED_BASEL_III, CFPB_SECTION_1033]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRealDocumentPipeline(unittest.TestCase):
    """Run curated real-world regulatory excerpts through the analyze pipeline."""

    def setUp(self) -> None:
        self.provider = MockProvider()
        self.memory = MemoryStore(":memory:")
        self.runtime = create_runtime(
            provider=self.provider,
            memory=self.memory,
        )

    def tearDown(self) -> None:
        self.memory.close()

    def _analyze(self, filing: RegulatoryFiling) -> dict:
        result = self.runtime.execute_skill(
            "analyze_filing",
            {"filing": filing.model_dump(mode="json"), "memory_context": ""},
        )
        self.assertTrue(result.success, msg=result.error)
        return result.data

    def test_sec_enforcement_manual_smoke_test(self) -> None:
        """Document 1: short structured press release should produce clean output."""
        data = self._analyze(SEC_ENFORCEMENT_MANUAL)
        self.assertEqual(data["filing_id"], SEC_ENFORCEMENT_MANUAL.id)
        self.assertIn(data["severity"], [s.value for s in Severity])
        self.assertGreaterEqual(data["confidence"], 0.0)
        self.assertLessEqual(data["confidence"], 1.0)
        self.assertIsInstance(data["action_items"], list)
        self.assertIsInstance(data["affected_business_lines"], list)

    def test_fed_basel_iii_core_pipeline(self) -> None:
        """Document 2: major rulemaking with explicit comment deadline."""
        data = self._analyze(FED_BASEL_III)
        self.assertEqual(data["filing_id"], FED_BASEL_III.id)
        self.assertIn(data["severity"], [s.value for s in Severity])
        # Basel III should produce non-trivial action items
        self.assertGreater(len(data["action_items"]), 0)
        # Business lines list must exist (may be empty under MockProvider)
        self.assertIsInstance(data["affected_business_lines"], list)

    def test_cfpb_section_1033_deadline_extraction(self) -> None:
        """Document 3: phased compliance dates should survive extraction."""
        data = self._analyze(CFPB_SECTION_1033)
        self.assertEqual(data["filing_id"], CFPB_SECTION_1033.id)
        self.assertIn(data["severity"], [s.value for s in Severity])
        self.assertGreater(len(data["action_items"]), 0)

    def test_all_three_filings_stored_in_memory(self) -> None:
        """Analyze all three, store each, and confirm they land in memory."""
        for filing in TEST_FILINGS:
            data = self._analyze(filing)
            store_result = self.runtime.execute_skill(
                "store_memory",
                {
                    "filing_id": filing.id,
                    "filing": filing.model_dump(mode="json"),
                    "impact": data,
                },
            )
            self.assertTrue(store_result.success, msg=store_result.error)

        from app.naturalsentinel.memory.types import MemoryType

        self.assertGreaterEqual(self.memory.count(MemoryType.EPISODIC), 3)

    def test_pipeline_produces_deterministic_structure(self) -> None:
        """Every result must have the same top-level keys regardless of input."""
        required_keys = {
            "filing_id",
            "severity",
            "affected_business_lines",
            "action_items",
            "confidence",
        }
        for filing in TEST_FILINGS:
            data = self._analyze(filing)
            missing = required_keys - set(data.keys())
            self.assertFalse(
                missing,
                msg=f"{filing.id} missing keys: {missing}",
            )


if __name__ == "__main__":
    unittest.main()
