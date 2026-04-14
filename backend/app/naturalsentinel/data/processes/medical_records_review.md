---
name: medical_records_review
version: "1.0"
doc_types: [medical]
description: Structured medical records review for insurance appeals, audits, and care coordination — covering diagnosis, treatment plan, lab results, billing alignment, and clinical documentation
author: NaturalSentinel
steps: 8
---

# Medical Records Review

## Step 1: Patient Identification & Demographics
- **instruction**: Verify patient identifying information: full name, date of birth, MRN, insurance ID, and primary care provider. Confirm consistent identification across all documents in the bundle. Flag any discrepancies or missing identifiers.
- **retrieval_query**: patient name date of birth MRN insurance ID demographics identification
- **target_sections**: [demographics, patient information, header, cover page]
- **depth**: overview
- **output**:
  - patient_name: string
  - date_of_birth: string
  - mrn: string
  - insurance_id: string
  - id_consistency: pass | fail | flagged
  - discrepancies: list of string
- **depends_on**: []

## Step 2: Chief Complaint & Presenting History
- **instruction**: Extract the chief complaint and history of present illness (HPI). Summarize onset, duration, character, severity, associated symptoms, and relevant prior history. Note whether the history is complete and internally consistent.
- **retrieval_query**: chief complaint history present illness HPI onset duration symptoms reason for visit
- **target_sections**: [chief complaint, HPI, history, presenting complaint, reason for visit]
- **depth**: overview
- **output**:
  - chief_complaint: string
  - hpi_summary: string
  - onset_date: string
  - symptom_severity: string
  - documentation_quality: complete | partial | insufficient
- **depends_on**: [1]

## Step 3: Diagnoses & ICD Codes
- **instruction**: Extract all diagnoses with their ICD-10 codes. For each, note: (1) primary vs. secondary vs. comorbidity status, (2) whether it is documented as confirmed, probable, or suspected, (3) whether the ICD code matches the clinical description. Flag any codes that appear unsupported by clinical documentation.
- **retrieval_query**: diagnosis ICD code diagnoses assessment impression problem list
- **target_sections**: [assessment, diagnosis, problem list, ICD, impression]
- **depth**: detail
- **output**:
  - diagnoses: list of {description, icd_code, status, documentation_support}
  - flagged_codes: list of {code, issue}
  - primary_diagnosis: string
- **depends_on**: [2]

## Step 4: Treatment Plan & Orders
- **instruction**: Review the treatment plan. For each treatment, intervention, or order, note: (1) the clinical indication, (2) dosage/frequency/duration (for medications), (3) ordering provider, and (4) whether the treatment aligns with the stated diagnosis. Flag any treatments without documented clinical indication or any contradictory orders.
- **retrieval_query**: treatment plan orders medications prescriptions interventions procedures plan
- **target_sections**: [plan, orders, medications, treatment, interventions, procedures]
- **depth**: detail
- **output**:
  - treatments: list of {type, description, indication, provider}
  - medications: list of {name, dosage, frequency, indication}
  - flagged_treatments: list of {treatment, issue}
  - diagnosis_alignment: pass | fail | flagged
- **depends_on**: [3]

## Step 5: Laboratory & Diagnostic Results
- **instruction**: Review all lab results, imaging, and diagnostic test results. For each, note: (1) the test ordered, (2) the result and reference range, (3) whether the result was acknowledged and acted upon, and (4) whether it supports or contradicts the stated diagnosis. Flag any abnormal results that appear to be unaddressed in the treatment plan.
- **retrieval_query**: laboratory results lab values imaging radiology diagnostic tests CBC BMP lipid panel
- **target_sections**: [labs, laboratory, results, imaging, diagnostics, radiology]
- **depth**: detail
- **output**:
  - lab_results: list of {test, result, reference_range, status, acted_upon}
  - imaging_findings: list of {study, findings, acted_upon}
  - unaddressed_abnormals: list of string
  - diagnosis_support: pass | fail | flagged
- **depends_on**: [3, 4]

## Step 6: Clinical Notes & Provider Documentation
- **instruction**: Review progress notes, SOAP notes, and provider documentation for quality and completeness. Check: (1) are notes signed and dated, (2) is there evidence of medical necessity for the level of service billed, (3) are there any documentation gaps or template/clone note concerns, (4) do notes reflect the actual services performed.
- **retrieval_query**: progress notes SOAP notes clinical documentation medical necessity level of service provider signature
- **target_sections**: [progress notes, SOAP, clinical notes, encounter notes, provider notes]
- **depth**: detail
- **output**:
  - notes_completeness: complete | partial | insufficient
  - medical_necessity_documented: boolean
  - clone_note_concern: boolean
  - documentation_gaps: list of string
  - concerns: list of string
- **depends_on**: [4, 5]

## Step 7: Billing & CPT Code Alignment
- **instruction**: Compare billed CPT codes against clinical documentation. For each billed service, verify: (1) the CPT code matches the documented service, (2) the level of service (E&M code) is supported by the documentation, (3) modifier use is appropriate, (4) there are no unbundling concerns. Flag any codes that appear unsupported or potentially overcoded.
- **retrieval_query**: CPT codes billing charges E&M evaluation management modifiers procedure codes
- **target_sections**: [billing, charges, CPT, procedure codes, claim, remittance]
- **depth**: detail
- **output**:
  - billed_services: list of {cpt_code, description, documentation_support, concern}
  - em_level_appropriate: pass | fail | flagged
  - modifier_issues: list of string
  - overcoding_concerns: list of string
  - undercoding_concerns: list of string
- **depends_on**: [6]

## Step 8: Appeal & Denial Analysis
- **instruction**: If this review is for an insurance appeal or denial response: identify the specific denial reason, assess whether clinical documentation supports medical necessity for the denied service, identify the strongest supporting evidence, and note any documentation gaps that need to be addressed before submission.
- **retrieval_query**: denial appeal medical necessity coverage criteria prior authorization not medically necessary
- **target_sections**: [denial, appeal, coverage, authorization, medical necessity criteria]
- **depth**: detail
- **output**:
  - denial_reason: string
  - supporting_evidence: list of string
  - documentation_gaps: list of string
  - appeal_strength: strong | moderate | weak
  - recommended_actions: list of string
- **depends_on**: [3, 4, 5, 6, 7]
