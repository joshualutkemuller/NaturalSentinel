# NaturalSentinel — Niche Healthcare Use Cases

The following use cases represent high-value, difficult-to-replicate applications
of NaturalSentinel in healthcare settings.  Each requires at least two of:

- **Simultaneous multi-agency monitoring** — most tools cover one agency
- **Temporal comparison across a rulemaking arc** — proposed → final → sub-regulatory
- **Entity-graph reasoning** — linking Drug → Manufacturer → Agency Precedent
- **Business-line scoping below the document level** — which paragraph affects which product line
- **Precedent memory** — pattern recognition across enforcement history

---

## 1. Cross-Agency Regulatory Conflict Detection for SUD Data in Care Coordination

**Who:** Behavioral health EHRs, integrated delivery networks, payers with mental health carve-outs

**The problem:**
42 CFR Part 2 (SAMHSA) requires explicit written consent before a SUD treatment
record can be shared — even for care coordination.  ONC's Information Blocking
Rule (45 CFR Part 171) simultaneously *prohibits* withholding electronic health
information.  These two rules are in direct tension for any system that surfaces
SUD data in a care coordination workflow.

**How NaturalSentinel helps:**
Monitors both SAMHSA and ONC simultaneously and uses its entity graph to detect
when a new ONC guidance on "exceptions to information blocking" intersects with
an active 42 CFR Part 2 rulemaking.  No existing alert tool maps cross-agency
intersections — they only monitor one agency at a time.

**Why it's hard to replicate:**
Requires persistent memory of the prior regulatory state of *both* rules and the
ability to reason about their conflict.  A plain search alert cannot do this.

**NaturalSentinel config:**
```python
agent = RegulatoryMonitorAgent(
    provider=provider,
    domains=[RegulatoryDomain.HHS, RegulatoryDomain.ONC],
    custom_business_lines={
        "sud_care_coordination": ["42 CFR Part 2", "ONC Information Blocking", "HIPAA TPO"],
    },
)
```

---

## 2. DEA Telehealth Controlled Substance Rules — By Schedule and Specialty

**Who:** Telehealth platforms, PBMs, multi-state prescribing groups

**The problem:**
Post-COVID DEA telehealth rules are still in flux.  The rules differ by:
- Controlled substance schedule (Schedule II vs. III–V)
- Prescribing specialty (psychiatry has a different carve-out than pain management)
- Modality (audio-only vs. audio-video)
- State of prescriber vs. state of patient

A telehealth company operating in 30 states with psychiatrists and internists
has an extremely specific compliance matrix that changes every time DEA issues
a new proposed rule, interim final rule, or extension of COVID-era exceptions.

**How NaturalSentinel helps:**
Its business-line impact mapping can be pre-configured for
`specialty × schedule × modality` so that a DEA rule change triggers an alert
scoped to exactly which service lines are affected — not a generic "DEA updated
telehealth rules" notification.

**Why it's hard to replicate:**
The intersection of modality, specialty, and schedule creates a sparse matrix
that requires structured metadata encoding most compliance tools don't support.

**NaturalSentinel config:**
```python
custom_business_lines={
    "telehealth_schedule_ii_psychiatry":   ["DEA 21 CFR 1306", "Ryan Haight Act"],
    "telehealth_schedule_iii_v_primary":   ["DEA 21 CFR 1306", "DEA Telemedicine Rules"],
    "telehealth_audio_only_prescribing":   ["DEA Special Registration", "State PDMP"],
}
```

---

## 3. Medicare Advantage Star Ratings Methodology Drift

**Who:** MA plan operators, risk adjustment vendors, provider groups in VBC contracts tied to star ratings

**The problem:**
CMS updates MA star ratings annually through the "Call Letter" and "Final Rule"
cycle.  Changes include:
- Cut point shifts (what score threshold maps to 3 vs. 4 stars)
- Measure weight adjustments (how much a HEDIS vs. CAHPS vs. HOS measure counts)
- New measure additions or removals
- Guardrail calculations that protect plans from large year-over-year swings

A single cut point shift on the medication adherence measure can cost a plan
hundreds of millions in quality bonuses.

**How NaturalSentinel helps:**
Its episodic memory tracks the proposed cut point from the Draft Call Letter,
then compares it against the Final Call Letter months later, flags the delta, and
maps it to specific HEDIS measure domains (which map to specific vendor contracts
or care management programs).  This is multi-step temporal reasoning that
requires memory across documents published months apart.

**Why it's hard to replicate:**
Requires temporal comparison of two documents in the same rulemaking cycle.
Alert systems fire once per document — not across the full rulemaking arc.

**Key metadata fields tracked:**
```python
{
    "regulation_id": "CMS-4201-F",          # MA Final Rule
    "rule_type": "final_rule",
    "affected_functions": ["star_ratings", "quality_bonus_payment", "HEDIS_measures"],
    "prior_cut_point": 82.0,                # from Draft Call Letter (in memory)
    "final_cut_point": 84.5,                # from Final Rule
    "delta": +2.5,
    "impacted_measure": "Medication Adherence for Diabetes Medications (D08)",
}
```

---

## 4. 340B Program Integrity Monitoring for Safety-Net Providers

**Who:** FQHCs, Ryan White HIV clinics, rural hospitals, children's hospitals, disproportionate share hospitals

**The problem:**
The 340B drug pricing program is under simultaneous pressure from:
- Manufacturer restriction letters (contract pharmacy access limitations)
- HRSA audit decision letters (interpretive precedent for "diversion")
- CMS payment rule changes (OPPS reimbursement for 340B drugs)
- Federal court decisions (manufacturers vs. HRSA)

A covered entity needs to know when a manufacturer restriction letter, an HRSA
ADR finding, and a CMS OPPS proposed rule all touch the same drug class at once.

**How NaturalSentinel helps:**
Its entity graph links:

```
Drug Class
  → Manufacturer
    → 340B Contract Pharmacy Restriction
      → HRSA ADR Precedent
        → CMS OPPS Payment Rate
```

When FDA approves a biosimilar that enters the 340B-eligible formulary, the
system proactively flags that its contract pharmacy availability is already
governed by an existing manufacturer restriction letter in memory.

**Why it's hard to replicate:**
Requires linking entities across four agencies (HRSA, CMS, FDA, federal courts)
that no single regulatory database covers.

**Agencies monitored simultaneously:**
```python
domains=[RegulatoryDomain.FDA, RegulatoryDomain.CMS, RegulatoryDomain.HRSA],
custom_fetchers=["hrsa_340b_adr", "federal_register_340b_docket"],
```

---

## 5. Medical Device Cybersecurity Regulatory Convergence

**Who:** Medical device manufacturers, hospital biomedical/IT departments, HDOs

**The problem:**
Three parallel regulatory streams now govern medical device cybersecurity:
- **FDA** 2023 Omnibus requirements for premarket submissions (SBOM, patch plans, coordinated vulnerability disclosure)
- **HIPAA Security Rule** (45 CFR § 164.312) — the device is a covered component of the ePHI ecosystem
- **CISA** healthcare sector advisories — not regulatory, but increasingly cited in OCR enforcement

A hospital biomedical team managing thousands of networked devices needs to know
when FDA issues updated premarket guidance that also changes what a "reasonable
HIPAA safeguard" looks like for a *legacy* device already deployed.

**How NaturalSentinel helps:**
FDA guidance is treated as `RegulatoryDomain.FDA`, OCR guidance as
`RegulatoryDomain.HHS`, and CISA advisories as a custom domain.  The agent maps
all three to the `biomedical_IT` business line and flags when either agency's
guidance changes the implied standard of care for existing devices — not just
new submissions.  Precedent memory prevents re-alerting on the same device class.

**Why it's hard to replicate:**
CISA advisories are not in the Federal Register.  NaturalSentinel's custom
fetchers cover non-standard sources, and precedent memory avoids alert fatigue
from repeated advisories on the same vulnerability class.

**Custom business line mapping:**
```python
custom_business_lines={
    "biomedical_IT": [
        "FDA 510(k) cybersecurity", "FDA PMA cybersecurity",
        "HIPAA § 164.312 technical safeguards", "CISA ICS-CERT healthcare",
        "NIST SP 800-66 Rev 2",
    ],
}
```

---

## 6. Prior Authorization FHIR Deadline Matrix by Payer Type

**Who:** Health IT vendors building payer-facing FHIR APIs, payers across multiple product lines

**The problem:**
CMS-9904-F has staggered compliance deadlines that differ by payer type:

| Payer type | Prior Auth API deadline | Decision notice deadline |
|---|---|---|
| Medicare Advantage plans | Jan 2026 | Jan 2026 |
| Medicaid FFS | Jan 2027 | Jan 2028 |
| CHIP | Jan 2027 | Jan 2028 |
| QHP issuers on exchanges | Jan 2027 | Jan 2028 |

A health IT vendor building a single FHIR prior auth platform for a client that
operates MA, Medicaid, and QHP lines of business needs to know when CMS issues
sub-regulatory guidance (FAQ, informational bulletin) that clarifies the API
spec for only *one* of those payer types — which changes the build priority.

**How NaturalSentinel helps:**
Business-line mapping is pre-configured with:
```python
custom_business_lines={
    "prior_auth_fhir_MA":       ["CMS-9904-F MA", "FHIR R4 Da Vinci PAS"],
    "prior_auth_fhir_medicaid": ["CMS-9904-F Medicaid", "FHIR R4 Da Vinci PAS"],
    "prior_auth_fhir_QHP":      ["CMS-9904-F QHP", "FHIR R4 Da Vinci PAS"],
}
```

When CMS issues a FAQ mentioning only MA plans, the impact assessment scopes it
to the MA workstream and flags it high priority while leaving Medicaid unaffected.

**Why it's hard to replicate:**
Requires sub-document scoping — identifying which portion of a multi-payer CMS
guidance applies to which line of business.  Most tools alert at the document level.

---

## 7. MSSP ACO Quality Measure Changes Cross-Referenced to VBC Contract Terms

**Who:** Health systems, ACOs, independent physician associations in value-based contracts

**The problem:**
CMS updates MSSP ACO quality measures annually.  When CMS proposes removing a
measure or adjusting benchmark methodology, it has a direct financial impact on
health systems whose commercial VBC contracts *reference MSSP benchmarks* as a
proxy for quality performance.

A health system CFO needs to know: "This proposed MSSP rule change, if finalized,
will reduce our achievable quality score under our Blue Cross VBC contract because
that contract uses MSSP measure weights."

**How NaturalSentinel helps:**
Memory stores prior-year MSSP measure weights as precedent, detects the delta in
the proposed rule, and maps the change to a `value_based_care` business line with
a flag that the contract cross-reference requires human review.

**Why it's hard to replicate:**
No existing tool links federal rulemaking to downstream commercial contract
implications.  This requires memory of the previous rulemaking cycle plus
entity-graph reasoning connecting `CMS Measure → MSSP Weight → VBC Contract Type`.

**Key entity relationships stored in memory graph:**
```
MSSP Quality Measure (ACO-45 Depression Screening)
  → Current measure weight: 1.0x
  → Proposed weight: removed
  → Affects: ["MSSP Track 1", "MSSP ENHANCED", "commercial VBC proxies"]
  → Precedent: "CMS removed 3 HEDIS measures in 2023 Final Rule with 6-month grace"
```

---

## Why These Seven Are the Hardest to Replicate

| Use case | Multi-agency | Temporal memory | Entity graph | Sub-doc scoping | Precedent |
|---|:---:|:---:|:---:|:---:|:---:|
| SUD cross-agency conflict | ✓ | | ✓ | | |
| DEA telehealth by schedule | | | | ✓ | ✓ |
| MA star ratings drift | | ✓ | | ✓ | |
| 340B program integrity | ✓ | | ✓ | | ✓ |
| Device cybersecurity convergence | ✓ | | ✓ | | ✓ |
| Prior auth FHIR by payer type | | ✓ | | ✓ | |
| MSSP ACO VBC alignment | | ✓ | ✓ | | ✓ |

A search alert, one-shot LLM query, or single-agency compliance platform can do
one of these.  NaturalSentinel is architected to do all five simultaneously.
