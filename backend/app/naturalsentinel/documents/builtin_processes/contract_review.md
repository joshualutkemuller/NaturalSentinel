---
name: contract_review
version: "1.0"
doc_types: [legal]
description: Standard commercial contract review checklist covering parties, definitions, key obligations, liability, termination, and governing law
author: NaturalSentinel
steps: 10
---

# Contract Review Checklist

## Step 1: Parties & Recitals
- **instruction**: Identify all parties, their legal entity types, and roles (buyer, seller, licensor, etc.). Confirm entity names are consistent throughout the document. Summarize the recitals to confirm the business purpose.
- **retrieval_query**: parties recitals legal entity names roles preamble
- **target_sections**: [parties, recitals, preamble, definitions]
- **depth**: overview
- **output**:
  - parties: list of {name, role, entity_type, jurisdiction}
  - recitals_summary: string
  - name_consistency: pass | fail | flagged
- **depends_on**: []

## Step 2: Defined Terms
- **instruction**: Review all defined terms. Flag circular definitions, ambiguous terms, or terms used but not defined. Note any defined terms that appear only once (potential drafting leftovers).
- **retrieval_query**: definitions defined terms meaning means refers to
- **target_sections**: [definitions, interpretation]
- **depth**: detail
- **output**:
  - defined_terms: list of {term, definition_summary}
  - flagged_terms: list of {term, issue}
  - undefined_used_terms: list of string
- **depends_on**: [1]

## Step 3: Key Obligations
- **instruction**: Identify the primary obligations of each party. For each obligation, note: (1) which party owes it, (2) the triggering condition, (3) the performance deadline, and (4) the consequence of non-performance.
- **retrieval_query**: obligations shall must deliver perform provide payment services deliverables
- **target_sections**: [services, obligations, payment, deliverables, scope]
- **depth**: detail
- **output**:
  - obligations: list of {party, obligation, trigger, deadline, consequence}
  - missing_obligations: list of string
- **depends_on**: [1, 2]

## Step 4: Payment & Pricing
- **instruction**: Review all payment provisions: amounts, schedules, invoicing requirements, late payment penalties, price adjustment mechanisms, and taxes. Flag any open-ended fee provisions or automatic price escalations without caps.
- **retrieval_query**: payment price fees invoicing schedule taxes late penalty escalation adjustment
- **target_sections**: [payment, fees, pricing, invoicing, taxes]
- **depth**: detail
- **output**:
  - payment_terms: string
  - fee_amounts: list of {description, amount, schedule}
  - escalation_clauses: list of string
  - tax_provisions: string
  - concerns: list of string
- **depends_on**: [3]

## Step 5: Representations & Warranties
- **instruction**: Review all representations and warranties. For each, note: (1) which party makes it, (2) the subject matter, (3) whether it is qualified by materiality or knowledge, and (4) whether it survives closing. Flag any that are unusual, one-sided, or potentially undeliverable.
- **retrieval_query**: representations warranties represents warrants knowledge material adverse
- **target_sections**: [representations, warranties, covenants]
- **depth**: detail
- **output**:
  - representations: list of {party, subject, qualifications}
  - flagged_reps: list of {representation, issue}
  - survival_period: string
- **depends_on**: [2]

## Step 6: Intellectual Property
- **instruction**: Review IP ownership, license grants, work-for-hire provisions, IP assignments, background IP vs. foreground IP, and any restrictions on use. Flag any IP ownership provisions that deviate from the party's standard position.
- **retrieval_query**: intellectual property ownership license grant work for hire assignment background foreground
- **target_sections**: [intellectual property, licenses, ownership, assignment]
- **depth**: detail
- **output**:
  - ip_ownership: list of {category, owner, basis}
  - license_grants: list of {grantor, grantee, scope, restrictions}
  - concerns: list of string
- **depends_on**: [2, 3]

## Step 7: Confidentiality & Data Protection
- **instruction**: Review confidentiality obligations, permitted disclosures, duration of obligations, and any data protection provisions (GDPR, CCPA, DPA requirements). Flag any carve-outs that are overly broad or any missing data breach notification requirements.
- **retrieval_query**: confidentiality non-disclosure personal data GDPR CCPA data protection privacy breach notification
- **target_sections**: [confidentiality, data protection, privacy, non-disclosure]
- **depth**: detail
- **output**:
  - confidentiality_scope: string
  - duration: string
  - permitted_disclosures: list of string
  - data_protection_obligations: list of string
  - concerns: list of string
- **depends_on**: [2]

## Step 8: Limitation of Liability & Indemnification
- **instruction**: Review liability cap provisions. Check: (1) aggregate cap amount or formula, (2) exclusions from cap (IP indemnity, confidentiality breach, fraud, willful misconduct), (3) consequential damages waiver, (4) mutual vs. one-sided structure, (5) indemnification scope and procedures.
- **retrieval_query**: limitation liability cap consequential damages waiver indemnification exclusions
- **target_sections**: [limitation of liability, indemnification, damages]
- **depth**: detail
- **output**:
  - liability_cap: string
  - cap_formula: string
  - exclusions_from_cap: list of string
  - consequential_waiver: pass | fail | flagged
  - mutual: boolean
  - indemnification_scope: string
  - concerns: list of string
- **depends_on**: [5]

## Step 9: Term & Termination
- **instruction**: Review the contract term, renewal provisions, and termination rights. Check: (1) initial term and renewal mechanics, (2) termination for convenience (notice period, payment obligations), (3) termination for cause (cure periods, triggering events), (4) effects of termination (survival clauses, transition obligations).
- **retrieval_query**: term expiration renewal termination convenience cause notice survival transition
- **target_sections**: [term, termination, renewal, survival, transition]
- **depth**: detail
- **output**:
  - initial_term: string
  - renewal_mechanism: string
  - termination_for_convenience: {notice_period, obligations}
  - termination_for_cause: {triggering_events, cure_period}
  - survival_provisions: list of string
  - concerns: list of string
- **depends_on**: [3, 8]

## Step 10: Governing Law & Dispute Resolution
- **instruction**: Review governing law, jurisdiction, and dispute resolution mechanisms. Check for: (1) which state/country law governs, (2) exclusive vs. non-exclusive jurisdiction, (3) arbitration vs. litigation, (4) venue, (5) jury trial waiver, (6) prevailing party fee shifting.
- **retrieval_query**: governing law jurisdiction arbitration dispute resolution venue jury waiver fee shifting
- **target_sections**: [governing law, dispute resolution, arbitration, jurisdiction]
- **depth**: detail
- **output**:
  - governing_law: string
  - dispute_resolution: string
  - jurisdiction: string
  - jury_waiver: boolean
  - fee_shifting: string
  - concerns: list of string
- **depends_on**: []
