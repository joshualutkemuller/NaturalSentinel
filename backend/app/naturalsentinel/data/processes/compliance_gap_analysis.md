---
name: compliance_gap_analysis
version: "1.0"
doc_types: [compliance, legal]
description: Structured compliance gap analysis — compares an internal policy, procedure, or control framework against applicable regulatory requirements to identify gaps, deficiencies, and required remediation actions
author: NaturalSentinel
steps: 8
---

# Compliance Gap Analysis

## Step 1: Regulatory Scope Identification
- **instruction**: Identify all regulatory frameworks, statutes, rules, and guidance documents that apply to the subject matter of this policy or procedure. For each, note: (1) the issuing authority, (2) the jurisdictions covered, (3) the effective date, (4) the specific obligations that are in scope. Flag any new or recently amended requirements that may not yet be reflected in the internal document.
- **retrieval_query**: regulatory requirements statutes rules regulations guidance effective date obligations scope applicability
- **target_sections**: [scope, applicability, regulatory framework, purpose, background]
- **depth**: overview
- **output**:
  - applicable_frameworks: list of {name, authority, jurisdiction, effective_date}
  - recent_amendments: list of {regulation, amendment_date, change_summary}
  - scope_gaps: list of string
- **depends_on**: []

## Step 2: Internal Policy Objectives & Controls Inventory
- **instruction**: Extract the stated objectives, scope, and key controls from the internal policy or procedure. For each control, note: (1) the control type (preventive, detective, corrective), (2) the control owner, (3) the frequency and testing method, and (4) whether it is documented or informal. Build an inventory of all stated controls.
- **retrieval_query**: policy objective control framework responsibilities ownership testing frequency documentation
- **target_sections**: [purpose, objectives, scope, controls, responsibilities, procedures]
- **depth**: detail
- **output**:
  - policy_objectives: list of string
  - controls: list of {control_id, description, type, owner, frequency, documented}
  - informal_controls: list of string
- **depends_on**: []

## Step 3: Obligation-to-Control Mapping
- **instruction**: For each regulatory obligation identified in Step 1, determine whether a corresponding control exists in the internal policy (Step 2). Create a mapping: obligation → control. For obligations with no matching control, mark as a gap. For obligations with a weak or partial control, mark as a deficiency.
- **retrieval_query**: obligation requirement control mapping coverage matrix shall must required prohibited
- **target_sections**: []
- **depth**: detail
- **output**:
  - mapping: list of {obligation, regulation, control_id, coverage_status}
  - gaps: list of {obligation, regulation, gap_description}
  - deficiencies: list of {obligation, regulation, control_id, deficiency_description}
- **depends_on**: [1, 2]

## Step 4: Risk Assessment of Gaps
- **instruction**: For each gap and deficiency identified in Step 3, assess the risk. Consider: (1) likelihood of regulatory examination or enforcement, (2) potential penalty or fine exposure, (3) reputational risk, (4) operational impact of non-compliance. Assign a risk tier (critical, high, medium, low) to each.
- **retrieval_query**: penalty fine enforcement examination examination risk material weakness deficiency
- **target_sections**: [enforcement, penalties, examination procedures, risk]
- **depth**: overview
- **output**:
  - risk_assessed_gaps: list of {obligation, gap_description, risk_tier, penalty_exposure, rationale}
  - critical_gaps: list of string
  - total_by_tier: {critical, high, medium, low}
- **depends_on**: [3]

## Step 5: Deadline & Effective Date Review
- **instruction**: Extract all compliance deadlines, implementation dates, effective dates, and transition periods from the regulatory requirements. For each, determine: (1) whether the internal policy already reflects the requirement, (2) how much time remains until the deadline, and (3) the remediation work required to meet it. Prioritize by urgency.
- **retrieval_query**: effective date compliance deadline implementation timeline transition period by which no later than
- **target_sections**: [effective date, implementation, timeline, transitional provisions]
- **depth**: detail
- **output**:
  - deadlines: list of {regulation, requirement, effective_date, days_remaining, internal_status}
  - overdue: list of {regulation, requirement, effective_date}
  - upcoming_90_days: list of {regulation, requirement, effective_date}
- **depends_on**: [1, 3]

## Step 6: Documentation & Record-Keeping Requirements
- **instruction**: Review all regulatory record-keeping, documentation, and reporting requirements. Check whether the internal policy: (1) specifies retention periods for required records, (2) defines the format and content of required documentation, (3) assigns responsibility for record maintenance, (4) addresses record destruction schedules. Flag any required records not addressed in the policy.
- **retrieval_query**: record keeping documentation retention reporting records books accounts preserve maintain
- **target_sections**: [records, documentation, reporting, retention, books and records]
- **depth**: detail
- **output**:
  - record_requirements: list of {regulation, record_type, retention_period, policy_coverage}
  - missing_record_provisions: list of {regulation, record_type}
  - retention_mismatches: list of {record_type, required_period, policy_period}
- **depends_on**: [1, 2]

## Step 7: Training & Awareness Requirements
- **instruction**: Identify any training, certification, or awareness requirements imposed by the applicable regulations. Check whether the internal policy: (1) requires training for relevant personnel, (2) specifies training frequency and content, (3) requires documentation of training completion, (4) addresses training for third parties or vendors. Flag any mandatory training not reflected in the policy.
- **retrieval_query**: training certification awareness annual required program personnel employees
- **target_sections**: [training, education, awareness, certification, personnel]
- **depth**: overview
- **output**:
  - training_requirements: list of {regulation, requirement, frequency, current_policy_coverage}
  - gaps: list of {regulation, requirement}
  - vendor_training_required: boolean
- **depends_on**: [1, 2]

## Step 8: Remediation Roadmap
- **instruction**: Synthesize all gaps, deficiencies, deadlines, and risk assessments into a prioritized remediation roadmap. For each item, specify: (1) the required action, (2) the priority (critical/high/medium/low), (3) the recommended remediation approach, (4) the deadline for completion, (5) the responsible party. Organize by priority tier.
- **retrieval_query**: remediation action plan corrective action implementation responsible owner deadline
- **target_sections**: []
- **depth**: overview
- **output**:
  - remediation_items: list of {action, priority, approach, deadline, owner, regulation_reference}
  - immediate_actions: list of string
  - total_gaps: integer
  - total_deficiencies: integer
  - estimated_effort: low | medium | high | very_high
- **depends_on**: [3, 4, 5, 6, 7]
