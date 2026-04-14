# Test Documents for NaturalSentinel + OpenViking

Real, publicly available regulatory documents for testing the ingestion,
analysis, and OpenViking storage pipeline end-to-end.

---

## SEC -- Securities and Exchange Commission

### 1. Enforcement Manual Update (Feb 2026)
- **Title**: SEC Division of Enforcement Announces Updates to Enforcement Manual
- **URL**: https://www.sec.gov/newsroom/press-releases/2026-20-secs-division-enforcement-announces-updates-enforcement-manual
- **Type**: Guidance
- **Why test this**: Short, structured press release. Tests basic ingestion. Affects broker-dealer operations, compliance procedures.
- **Expected severity**: MEDIUM
- **Expected business lines**: Investment Banking, Public Equities, Audit & Assurance

### 2. FY2025 Enforcement Results (2026)
- **Title**: SEC Announces Enforcement Results for Fiscal Year 2025
- **URL**: https://www.sec.gov/newsroom/press-releases/2026-34
- **Type**: Notice
- **Why test this**: Statistical summary with dollar figures ($17.9B in monetary relief, 456 actions). Tests numeric extraction.
- **Expected severity**: LOW (informational)

### 3. 2026 Examination Priorities
- **Title**: SEC Division of Examinations Announces 2026 Priorities
- **URL**: https://www.sec.gov/newsroom/press-releases/2025-132-sec-division-examinations-announces-2026-priorities
- **Type**: Guidance
- **Why test this**: Forward-looking document. Tests extraction of compliance deadlines and focus areas (Reg S-P amendments, fiduciary duty, custody rule).
- **Expected severity**: HIGH
- **Expected business lines**: All SEC-regulated entities

---

## Federal Reserve

### 4. Basel III Capital Framework Modernization (March 2026)
- **Title**: Agencies request comment on proposals to modernize the regulatory capital framework
- **URL**: https://www.federalreserve.gov/newsevents/pressreleases/bcreg20260319a.htm
- **Type**: Proposed Rule
- **Why test this**: Major multi-agency rulemaking (Fed + OCC + FDIC). Tests cross-domain detection. Comment deadline June 18, 2026.
- **Expected severity**: CRITICAL
- **Expected business lines**: Capital Optimization, RWA Modelling, Leverage Ratio, Commercial Banking, Capital Planning

### 5. Vice Chair Bowman Speech on Basel III (March 2026)
- **Title**: Speech by Vice Chair for Supervision Bowman on Basel III and bank capital rules
- **URL**: https://www.federalreserve.gov/newsevents/speech/bowman20260312a.htm
- **Type**: Guidance (speech)
- **Why test this**: Forward guidance from a Fed governor. Tests the system's ability to extract regulatory signals from unstructured speech text.
- **Expected severity**: MEDIUM

### 6. Capital Standards Final Rule (Nov 2025)
- **Title**: Agencies issue final rule to modify certain regulatory capital standards
- **URL**: https://www.federalreserve.gov/newsevents/pressreleases/bcreg20251125b.htm
- **Type**: Final Rule
- **Why test this**: Already effective (April 1, 2026). Reduces disincentives for US Treasury market intermediation. Tests final rule impact analysis.
- **Expected severity**: HIGH
- **Expected business lines**: Capital Markets, Treasury & ALM, Capital Optimization

---

## CFPB -- Consumer Financial Protection Bureau

### 7. Personal Financial Data Rights (Section 1033)
- **Title**: Personal Financial Data Rights Reconsideration
- **URL**: https://www.federalregister.gov/documents/2025/08/22/2025-16139/personal-financial-data-rights-reconsideration
- **Type**: Final Rule (reconsideration)
- **Why test this**: Major consumer data rule. First compliance date June 30, 2026. Tests deadline extraction from complex multi-phase rule.
- **Expected severity**: CRITICAL
- **Expected business lines**: Consumer Lending, Credit Cards, Fintech Partnerships

### 8. Data Broker Rule (Regulation V)
- **Title**: Protecting Americans from Harmful Data Broker Practices
- **URL**: https://www.consumerfinance.gov/rules-policy/rules-under-development/protecting-americans-from-harmful-data-broker-practices-regulation-v/
- **Type**: Proposed Rule
- **Why test this**: New domain (data privacy). Tests cross-domain tagging (CFPB + privacy).
- **Expected severity**: HIGH
- **Expected business lines**: Fintech Partnerships, Consumer Lending, Collections

### 9. Small Business Lending (Section 1071)
- **Title**: Small Business Lending Rule Reconsideration
- **URL**: https://www.consumerfinance.gov/1071-rule/
- **Type**: Proposed Rule
- **Why test this**: Contested rule with ongoing litigation. Tests the system's ability to flag legal uncertainty.
- **Expected severity**: HIGH

---

## CFTC -- Commodity Futures Trading Commission

### 10. Margin Adequacy for FCMs
- **Title**: Regulations to Address Margin Adequacy and Treatment of Separate Accounts by FCMs
- **URL**: https://www.federalregister.gov/documents/2025/01/22/2024-31177/regulations-to-address-margin-adequacy-and-to-account-for-the-treatment-of-separate-accounts-by
- **Type**: Final Rule
- **Why test this**: Two-phase compliance (July 2025 for clearing members, January 2026 for all FCMs). Tests multi-date deadline extraction.
- **Expected severity**: HIGH
- **Expected business lines**: Derivatives / Swaps, Initial Margin, Counterparty Credit Risk

---

## FINRA

### 11. Customer Fraud Protection Modernization (Reg Notice 26-02)
- **Title**: FINRA Seeks Comment on Proposed Amendments to Rules 4512, 2165, and Proposed Rule 2166
- **URL**: https://www.finra.org/rules-guidance/notices/26-02
- **Type**: Proposed Rule
- **Why test this**: Multiple rule changes in a single notice. Tests extraction of distinct action items from one document.
- **Expected severity**: MEDIUM
- **Expected business lines**: Broker-Dealer Operations, Customer Margin Accounts

### 12. 2026 Annual Regulatory Oversight Report
- **Title**: 2026 FINRA Annual Regulatory Oversight Report
- **URL**: https://www.finra.org/rules-guidance/guidance/reports/2026-finra-annual-regulatory-oversight-report
- **Type**: Guidance
- **Why test this**: Long, multi-topic document. Includes GenAI section. Tests the system's ability to extract multiple distinct regulatory themes from one large document. Good test for OpenViking L0/L1/L2 tiering.
- **Expected severity**: MEDIUM

---

## OCC / FDIC (Joint)

### 13. Regulatory Capital Modernization (Category I/II Banks)
- **Title**: Regulatory Capital Rule: Category I and II Banking Organizations
- **URL**: https://www.federalregister.gov/documents/2026/03/27/2026-05959/regulatory-capital-rule-category-i-and-ii-banking-organizations-banking-organizations-with
- **Type**: Proposed Rule
- **Why test this**: Joint Fed/OCC/FDIC rulemaking. ~1000+ page Federal Register document. Tests ingestion of very large documents. Comment deadline June 18, 2026.
- **Expected severity**: CRITICAL
- **Expected business lines**: Capital Optimization, RWA Modelling, SA-CCR, Leverage Ratio

### 14. Standardized Approach for Risk-Weighted Assets
- **Title**: Regulatory Capital Rules: Standardized Approach for Risk-Weighted Assets
- **URL**: https://www.federalregister.gov/documents/2026/03/27/2026-05960/regulatory-capital-rules-regulatory-capital-and-standardized-approach-for-risk-weighted-assets
- **Type**: Proposed Rule
- **Why test this**: Companion to #13. Tests the system's ability to detect and link related rulemakings.
- **Expected severity**: CRITICAL

### 15. FDIC Stablecoin Framework
- **Title**: Payment Stablecoins Application Framework for FDIC-Supervised Institutions
- **Source**: FDIC proposed rulemaking, December 2025. Comments extended to May 18, 2026.
- **Type**: Proposed Rule
- **Why test this**: Novel domain (crypto/stablecoins). Tests cross-domain tagging (FDIC + digital assets).
- **Expected severity**: HIGH
- **Expected business lines**: Digital Assets / Crypto, Payments, Commercial Banking

---

## EPA -- Environmental Protection Agency

### 16. PFAS Reporting Scope Changes
- **Title**: PFAS Data Reporting and Recordkeeping Under TSCA; Change to Submission Period
- **URL**: https://www.federalregister.gov/documents/2025/05/13/2025-08168/perfluoroalkyl-and-polyfluoroalkyl-substances-pfas-data-reporting-and-recordkeeping-under-the-toxic
- **Type**: Proposed Rule
- **Why test this**: Environmental regulation with financial impact (reporting costs, liability). Tests the analysis of non-financial regulation that has financial implications.
- **Expected severity**: MEDIUM
- **Expected business lines**: Manufacturing, Insurance (Environmental)

---

## OFAC -- Treasury Sanctions (not yet fetching -- new source)

### 17. Recent SDN List Updates
- **Title**: Archive of Changes to OFAC's Sanctions Lists
- **URL**: https://ofac.treasury.gov/specially-designated-nationals-list-sdn-list/archive-of-changes-to-the-sdn-list
- **Type**: Enforcement
- **Why test this**: Bulk data source. Tests ability to parse CSV/XML format. Time-critical compliance data.
- **Expected severity**: CRITICAL

### 18. Recent Sanctions Actions
- **Title**: OFAC Recent Actions
- **URL**: https://ofac.treasury.gov/recent-actions
- **Type**: Enforcement
- **Why test this**: Mixed content (designations, removals, general licenses). Tests categorization.
- **Expected severity**: HIGH

---

## Federal Register API -- Direct Test URLs

These are structured JSON API calls you can use to test the Federal Register fetcher directly:

```bash
# Recent SEC proposed rules (last 30 days)
curl "https://www.federalregister.gov/api/v1/documents.json?conditions[agencies][]=securities-and-exchange-commission&conditions[type][]=PRORULE&per_page=5&order=newest"

# Recent Fed final rules (last 60 days)
curl "https://www.federalregister.gov/api/v1/documents.json?conditions[agencies][]=federal-reserve-system&conditions[type][]=RULE&per_page=5&order=newest"

# Recent CFPB documents (all types)
curl "https://www.federalregister.gov/api/v1/documents.json?conditions[agencies][]=consumer-financial-protection-bureau&per_page=10&order=newest"

# Recent EPA PFAS-related documents
curl "https://www.federalregister.gov/api/v1/documents.json?conditions[agencies][]=environmental-protection-agency&conditions[term]=PFAS&per_page=5&order=newest"

# Recent CFTC margin-related documents
curl "https://www.federalregister.gov/api/v1/documents.json?conditions[agencies][]=commodity-futures-trading-commission&conditions[term]=margin&per_page=5&order=newest"
```

---

## Suggested Test Sequence

### Quick smoke test (5 min)
Ingest documents #1 (SEC enforcement manual) and #11 (FINRA 26-02).
Both are short, well-structured, and should produce clean analysis.

### Core pipeline test (30 min)
Ingest documents #4 (Basel III capital), #7 (CFPB Section 1033), and #10 (CFTC margin).
These test: multi-agency rules, deadline extraction, cross-domain correlation.

### Stress test (2 hours)
Ingest documents #12 (FINRA annual report) and #13 (OCC capital rule).
These are very large documents. Tests: chunking, L0/L1/L2 tiering,
token budget management, long-document summarization.

### Cross-domain correlation test
Ingest #4, #13, and #14 together. All three are related capital rules
from the same joint rulemaking. The system should detect and link them.

### Novel domain test
Ingest #15 (FDIC stablecoins) and #8 (CFPB data brokers).
These are emerging regulatory areas. Tests whether the LLM can handle
topics not well-represented in training data.
