"""End-to-end pipeline test using excerpts from real healthcare regulatory documents.

Runs three curated filings covering telehealth and scheduled (controlled
substance) drug prescribing through the ``analyze_filing`` skill with the
MockProvider to verify the pipeline handles healthcare/DEA/CMS subject
matter without needing live API calls.

Documents:
    1. DEA Fourth Temporary Extension of COVID-19 Telemedicine Flexibilities
       (Dec 31, 2025) — controlled substance prescribing via telehealth
    2. DEA/HHS Expansion of Buprenorphine Treatment via Telemedicine
       (March 2025) — Schedule III narcotic for opioid use disorder
    3. CMS CY 2026 Medicare Physician Fee Schedule Final Rule (Oct 2025) —
       Medicare telehealth services list, supervision, and frequency limits

Note: NaturalSentinel does not currently have dedicated DEA / CMS / HHS
domain enum values, so all three filings are tagged ``RegulatoryDomain.FDA``
as the closest existing healthcare domain. Adding ``DEA`` and ``CMS`` as
first-class domains would be a future enhancement.
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
# Test fixtures — excerpts drawn from publicly available healthcare regulations
# ---------------------------------------------------------------------------

DEA_FOURTH_EXTENSION = RegulatoryFiling(
    id="DEA-2025-1231-FOURTH-EXT",
    title=(
        "Fourth Temporary Extension of COVID-19 Telemedicine Flexibilities "
        "for Prescription of Controlled Medications"
    ),
    domain=RegulatoryDomain.FDA,
    source_url=(
        "https://www.federalregister.gov/documents/2025/12/31/2025-24123/"
        "fourth-temporary-extension-of-covid-19-telemedicine-flexibilities-"
        "for-prescription-of-controlled"
    ),
    published_date="2025-12-31",
    change_type=ChangeType.AMENDMENT,
    raw_text=(
        "The Drug Enforcement Administration (DEA), jointly with the Department "
        "of Health and Human Services (HHS), is issuing this fourth temporary "
        "extension of the COVID-19 telemedicine flexibilities for the "
        "prescription of controlled medications. Under the extended "
        "flexibilities, DEA-registered practitioners are authorized to prescribe "
        "schedule II-V controlled medications via audio-video telemedicine "
        "encounters, including schedule III-V narcotic controlled medications "
        "approved by the Food and Drug Administration for maintenance and "
        "withdrawal management treatment of opioid use disorder via audio-only "
        "telemedicine encounters, without having ever conducted an in-person "
        "medical evaluation of the patient. This rule is effective January 1, "
        "2026 through December 31, 2026. Practitioners must comply with all "
        "other applicable Federal and State laws, including reporting to State "
        "Prescription Drug Monitoring Programs (PDMPs). Failure to comply may "
        "result in administrative action, civil money penalties, or revocation "
        "of DEA registration. Telemedicine providers, digital health platforms, "
        "and pharmacy operators should review prescribing workflows immediately."
    ),
)

DEA_BUPRENORPHINE_TELEMEDICINE = RegulatoryFiling(
    id="DEA-2025-0324-BUPRENORPHINE",
    title=(
        "Expansion of Buprenorphine Treatment via Telemedicine Encounter "
        "and Continuity of Care via Telemedicine for Veterans Affairs Patients"
    ),
    domain=RegulatoryDomain.FDA,
    source_url=(
        "https://www.federalregister.gov/documents/2025/03/24/2025-05007/"
        "expansion-of-buprenorphine-treatment-via-telemedicine-encounter-"
        "and-continuity-of-care-via"
    ),
    published_date="2025-03-24",
    change_type=ChangeType.FINAL_RULE,
    raw_text=(
        "The Drug Enforcement Administration (DEA), jointly with the Department "
        "of Health and Human Services (HHS), is issuing this final rule to "
        "expand the prescribing of buprenorphine, a schedule III narcotic "
        "controlled substance approved by the FDA for the treatment of opioid "
        "use disorder, via telemedicine encounter. The rule authorizes "
        "DEA-registered practitioners to prescribe an initial six-month supply "
        "of buprenorphine following an audio-only or audio-video telemedicine "
        "encounter, without a prior in-person medical evaluation. The rule also "
        "establishes a parallel framework for Veterans Affairs patients to "
        "receive continuity of care for any DEA-scheduled medication via "
        "telemedicine, provided that a VA practitioner has previously conducted "
        "an in-person evaluation. The effective date is December 31, 2025. "
        "Practitioners must check the relevant State Prescription Drug "
        "Monitoring Program prior to issuing the prescription, must maintain "
        "records of the telemedicine encounter for two years, and must comply "
        "with all relevant federal and state controlled substance laws. This "
        "rule materially affects opioid treatment programs, addiction medicine "
        "specialists, telehealth providers, and Veterans Health Administration "
        "operations."
    ),
)

CMS_2026_PFS_TELEHEALTH = RegulatoryFiling(
    id="CMS-2025-1105-PFS-2026",
    title=(
        "Medicare and Medicaid Programs; CY 2026 Payment Policies Under the "
        "Physician Fee Schedule and Other Changes to Part B Payment Policies"
    ),
    domain=RegulatoryDomain.FDA,
    source_url=(
        "https://www.federalregister.gov/documents/2025/11/05/2025-19787/"
        "medicare-and-medicaid-programs-cy-2026-payment-policies-under-the-"
        "physician-fee-schedule-and-other"
    ),
    published_date="2025-11-05",
    change_type=ChangeType.FINAL_RULE,
    raw_text=(
        "The Centers for Medicare & Medicaid Services (CMS) is issuing this "
        "final rule for the Calendar Year 2026 Medicare Physician Fee Schedule. "
        "Among the telehealth-related provisions, CMS is finalizing a "
        "streamlined process for adding services to the Medicare Telehealth "
        "Services List, removing the prior distinction between provisional and "
        "permanent services and limiting review to whether the service can be "
        "furnished using an interactive, two-way audio-video telecommunications "
        "system. CMS is permanently adopting a definition of direct supervision "
        "that allows supervision through real-time audio and visual interactive "
        "telecommunications (excluding audio-only). CMS is also finalizing the "
        "permanent removal of frequency limitations for subsequent inpatient "
        "visits, subsequent nursing facility visits, and critical care "
        "consultations. Pursuant to recent legislation, Medicare patients may "
        "continue to receive telehealth services for non-behavioral or mental "
        "health care in their home with no geographic restrictions on the "
        "originating site, and may use audio-only platforms, through "
        "December 31, 2027. Policy changes are effective on or after January 1, "
        "2026. Hospitals, physician groups, telehealth platforms, accountable "
        "care organizations, and Medicare Advantage plans must update billing "
        "and supervision workflows to align with the new definitions."
    ),
)

TEST_FILINGS = [
    DEA_FOURTH_EXTENSION,
    DEA_BUPRENORPHINE_TELEMEDICINE,
    CMS_2026_PFS_TELEHEALTH,
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHealthcarePipeline(unittest.TestCase):
    """Run curated healthcare regulatory excerpts through the analyze pipeline."""

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

    def test_dea_fourth_extension_smoke_test(self) -> None:
        """Document 1: telemedicine flexibilities for controlled medications."""
        data = self._analyze(DEA_FOURTH_EXTENSION)
        self.assertEqual(data["filing_id"], DEA_FOURTH_EXTENSION.id)
        self.assertIn(data["severity"], [s.value for s in Severity])
        self.assertGreaterEqual(data["confidence"], 0.0)
        self.assertLessEqual(data["confidence"], 1.0)
        self.assertIsInstance(data["action_items"], list)
        self.assertIsInstance(data["affected_business_lines"], list)

    def test_dea_buprenorphine_telemedicine_final_rule(self) -> None:
        """Document 2: schedule III narcotic telemedicine prescribing rule."""
        data = self._analyze(DEA_BUPRENORPHINE_TELEMEDICINE)
        self.assertEqual(data["filing_id"], DEA_BUPRENORPHINE_TELEMEDICINE.id)
        self.assertIn(data["severity"], [s.value for s in Severity])
        # Final rule with concrete effective date should produce action items
        self.assertGreater(len(data["action_items"]), 0)
        self.assertIsInstance(data["affected_business_lines"], list)

    def test_cms_2026_pfs_telehealth_provisions(self) -> None:
        """Document 3: large multi-topic CMS final rule with telehealth changes."""
        data = self._analyze(CMS_2026_PFS_TELEHEALTH)
        self.assertEqual(data["filing_id"], CMS_2026_PFS_TELEHEALTH.id)
        self.assertIn(data["severity"], [s.value for s in Severity])
        self.assertGreater(len(data["action_items"]), 0)
        self.assertIsInstance(data["affected_business_lines"], list)

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
        """Every healthcare result must have the same top-level keys."""
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

    def test_telehealth_filings_share_subject_matter(self) -> None:
        """Verify all three documents reference telemedicine/telehealth."""
        for filing in TEST_FILINGS:
            text_lower = filing.raw_text.lower()
            self.assertTrue(
                "telemedicine" in text_lower or "telehealth" in text_lower,
                msg=f"{filing.id} should mention telemedicine or telehealth",
            )

    def test_controlled_substance_filings_reference_schedules(self) -> None:
        """Both DEA filings should reference DEA controlled substance schedules."""
        for filing in [DEA_FOURTH_EXTENSION, DEA_BUPRENORPHINE_TELEMEDICINE]:
            text_lower = filing.raw_text.lower()
            self.assertIn(
                "schedule",
                text_lower,
                msg=f"{filing.id} should reference DEA schedule",
            )


if __name__ == "__main__":
    unittest.main()
