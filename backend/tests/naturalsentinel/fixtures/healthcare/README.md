# Healthcare Pipeline Test Documents

Source documents exercised by
`backend/tests/naturalsentinel/test_pipeline_healthcare_docs.py`.

The test currently embeds hand-curated **excerpts** of each filing as inline
Python string literals (see the `raw_text=` fields on each
`RegulatoryFiling` fixture). The full source documents have **not** been
checked into the repository; this directory is the agreed-upon location for
caching them once they can be fetched from a network that allows outbound
HTTPS to `federalregister.gov`.

To populate this directory, run (from any environment with internet access):

```bash
mkdir -p backend/tests/naturalsentinel/fixtures/healthcare
cd backend/tests/naturalsentinel/fixtures/healthcare
for doc in 2025-24123 2025-05007 2025-19787; do
  curl -fsSL -o "${doc}.json" "https://www.federalregister.gov/api/v1/documents/${doc}.json"
  curl -fsSL -o "${doc}.html" "https://www.federalregister.gov/documents/full_text/html/${doc}.html"
done
```

Once cached, the test can be migrated to load `raw_text` from these files
instead of the inline string literals.

---

## Document 1 — DEA Fourth Temporary Extension (Doc 2025-24123)

- **Title**: Fourth Temporary Extension of COVID-19 Telemedicine
  Flexibilities for Prescription of Controlled Medications
- **Agency**: Drug Enforcement Administration (DEA), jointly with HHS
- **Type**: Amendment / Temporary extension
- **Published**: 2025-12-31
- **Effective**: January 1, 2026 through December 31, 2026
- **Subject**: Authorization for DEA-registered practitioners to prescribe
  schedule II–V controlled medications via audio-video telemedicine
  encounters (and schedule III–V narcotics for OUD via audio-only) without
  a prior in-person evaluation.
- **HTML**:
  https://www.federalregister.gov/documents/2025/12/31/2025-24123/fourth-temporary-extension-of-covid-19-telemedicine-flexibilities-for-prescription-of-controlled
- **JSON API**:
  https://www.federalregister.gov/api/v1/documents/2025-24123.json

## Document 2 — DEA/HHS Buprenorphine via Telemedicine (Doc 2025-05007)

- **Title**: Expansion of Buprenorphine Treatment via Telemedicine
  Encounter and Continuity of Care via Telemedicine for Veterans Affairs
  Patients
- **Agency**: Drug Enforcement Administration (DEA), jointly with HHS
- **Type**: Final Rule
- **Published**: 2025-03-24
- **Effective**: December 31, 2025
- **Subject**: Authorizes DEA-registered practitioners to prescribe an
  initial six-month supply of buprenorphine (schedule III narcotic, FDA-
  approved for OUD) via audio-only or audio-video telemedicine without a
  prior in-person evaluation. Establishes a parallel framework for VA
  patients to receive any DEA-scheduled medication via telemedicine
  provided a VA practitioner has previously conducted an in-person
  evaluation.
- **HTML**:
  https://www.federalregister.gov/documents/2025/03/24/2025-05007/expansion-of-buprenorphine-treatment-via-telemedicine-encounter-and-continuity-of-care-via
- **JSON API**:
  https://www.federalregister.gov/api/v1/documents/2025-05007.json

## Document 3 — CMS CY 2026 Physician Fee Schedule (Doc 2025-19787)

- **Title**: Medicare and Medicaid Programs; CY 2026 Payment Policies
  Under the Physician Fee Schedule and Other Changes to Part B Payment
  Policies
- **Agency**: Centers for Medicare & Medicaid Services (CMS)
- **Type**: Final Rule
- **Published**: 2025-11-05
- **Effective**: On or after January 1, 2026
- **Subject**: CY 2026 Medicare Physician Fee Schedule. Telehealth
  provisions include a streamlined process for adding services to the
  Medicare Telehealth Services List, a permanent definition of direct
  supervision via real-time audio-video, and permanent removal of
  frequency limits for subsequent inpatient/nursing-facility visits and
  critical care consultations. Audio-only and home-as-originating-site
  flexibilities for non-behavioral telehealth extended through
  December 31, 2027.
- **HTML**:
  https://www.federalregister.gov/documents/2025/11/05/2025-19787/medicare-and-medicaid-programs-cy-2026-payment-policies-under-the-physician-fee-schedule-and-other
- **JSON API**:
  https://www.federalregister.gov/api/v1/documents/2025-19787.json

---

## Domain mapping

`RegulatoryDomain` now includes `DEA`, `CMS`, and `HHS` as first-class
enum values. Each filing uses its native domain tag. The Federal Register
fetcher maps these to the correct agency slugs via `DOMAIN_TO_AGENCY` in
`backend/app/naturalsentinel/fetchers/live/federal_register.py`.
