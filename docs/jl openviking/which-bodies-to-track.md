# Which Regulatory Bodies to Track

Ranked by impact, API quality, and relevance to the NaturalSentinel use case.

---

## Tier 1 -- Must Have (track from day one)

These are the core agencies. All have free, structured APIs or feeds.

### SEC (Securities and Exchange Commission)
- **Why**: Governs public markets, broker-dealers, investment advisers. Every financial firm cares.
- **What to watch**: Proposed/final rules, enforcement actions, no-action letters, staff guidance, exam priorities
- **Sources**: Federal Register API + EDGAR EFTS (both already built)
- **Current status**: **Already fetching**

### Federal Reserve
- **Why**: Sets monetary policy, bank capital rules, payment system oversight. Basel III endgame lives here.
- **What to watch**: Proposed rules, final rules, governor speeches, testimony, supervision guidance
- **Sources**: Federal Register API (already built) + Fed speeches JSON feed (not built)
- **Current status**: **Partially fetching** (rules yes, speeches no)
- **Key active items**: Basel III capital framework modernization (comments due June 18, 2026)

### CFPB (Consumer Financial Protection Bureau)
- **Why**: Consumer lending, credit cards, mortgages, fintech. Aggressive enforcement cadence.
- **What to watch**: Proposed rules, enforcement actions, supervisory highlights, complaint trends
- **Sources**: Federal Register API (built) + CFPB complaints API (not built)
- **Current status**: **Partially fetching**
- **Key active items**: Personal Financial Data Rights (Section 1033, compliance starts June 30, 2026), Data broker rule (Regulation V), Small business lending (Section 1071)

### OCC (Office of the Comptroller of the Currency)
- **Why**: Primary regulator for national banks. Capital, lending, model risk.
- **What to watch**: Proposed rules, bulletins, consent orders, enforcement actions
- **Sources**: Federal Register API (built) + OCC enforcement search (not built)
- **Current status**: **Partially fetching**
- **Key active items**: Regulatory capital modernization (joint with Fed/FDIC), CRA rescission

### FINRA (Financial Industry Regulatory Authority)
- **Why**: Self-regulatory org for broker-dealers. Margin, securities lending, outside activities.
- **What to watch**: Regulatory notices, rule filings, Annual Regulatory Oversight Report
- **Sources**: FINRA notices scraper (built)
- **Current status**: **Already fetching**
- **Key active items**: Rule 3290 (outside activities), customer fraud protection modernization, arbitration modernization, Financial Intelligence Fusion Center (FIFC) launching 2026

### FDIC (Federal Deposit Insurance Corporation)
- **Why**: Deposit insurance, bank resolution, co-regulator on capital rules.
- **What to watch**: Proposed rules, financial institution letters, enforcement actions
- **Sources**: Federal Register API (built)
- **Current status**: **Partially fetching**
- **Key active items**: Payment stablecoins framework (comments due May 18, 2026), CRA rescission (joint)

### CFTC (Commodity Futures Trading Commission)
- **Why**: Derivatives, swaps, futures. Margin requirements, clearing mandates.
- **What to watch**: Proposed rules, no-action letters, staff advisories, enforcement
- **Sources**: Federal Register API (built)
- **Current status**: **Partially fetching**
- **Key active items**: Margin adequacy for FCMs (compliance Jan 2026), cross-margining (CME/FICC)

---

## Tier 2 -- Should Have (add within first quarter)

### OFAC / Treasury (Office of Foreign Assets Control)
- **Why**: Sanctions compliance is non-negotiable for any bank, fintech, or payment processor. SDN list changes are time-critical.
- **What to watch**: SDN list additions/removals, new sanctions programs, general licenses
- **Sources**: SDN bulk download (CSV/XML), sanctions list search API, recent actions feed
- **API**: `https://sanctionssearch.ofac.treas.gov/` + `https://ofac.treasury.gov/recent-actions`
- **Cadence**: Daily (SDN changes happen multiple times per week)
- **Priority**: HIGH -- compliance-critical, time-sensitive

### EPA (Environmental Protection Agency)
- **Why**: PFAS regulation, emissions standards, Superfund liability. Affects manufacturing, energy, real estate, insurance.
- **What to watch**: Proposed rules, final rules, enforcement actions, TSCA reporting
- **Sources**: Federal Register API (built)
- **Current status**: **Already fetching**
- **Key active items**: PFAS drinking water standards (compliance extended to 2031), PFAS reporting scope changes, oil & gas emissions (NSPS amendments finalizing April 2026), risk management programs (comments due May 2026)

### Basel Committee (BIS/BCBS)
- **Why**: International capital standards that flow into Fed/OCC/FDIC rules. Affects every global bank.
- **What to watch**: Consultative documents, final standards, working papers
- **Sources**: BIS publications scraper (built)
- **Current status**: **Already fetching**
- **Cadence**: Monthly (publishes infrequently)

### Congress.gov
- **Why**: Legislation is upstream of regulation. Bills that pass committee signal future rulemaking.
- **What to watch**: Financial services committee bills, banking committee hearings, floor votes
- **Sources**: Congress.gov API (`https://api.congress.gov/v3/`)
- **API**: Free, API key required (instant signup)
- **Priority**: MEDIUM -- leading indicator, not actionable itself

### FDA (Food and Drug Administration)
- **Why**: Medical devices, pharma, digital health, clinical trials. Major if you cover healthcare/biotech.
- **What to watch**: Proposed rules, guidance documents, device approvals, enforcement
- **Sources**: Federal Register API (built)
- **Current status**: **Already fetching**

---

## Tier 3 -- Nice to Have (phase 2)

### EU Regulatory (EUR-Lex / ESMA / EBA)
- **Why**: GDPR, MiCA (crypto), AI Act, DORA (digital resilience), MiFID. Extraterritorial reach.
- **Sources**: EUR-Lex SPARQL/REST API
- **Effort**: High (complex API, XML/RDF parsing)
- **Priority**: Only if you have EU-exposed clients

### UK FCA / PRA
- **Why**: Post-Brexit divergence. FCA is aggressive on fintech/crypto enforcement.
- **Sources**: HTML scrape (no structured API)
- **Priority**: Only if UK operations are in scope

### NIST / CISA (Cybersecurity)
- **Why**: Cybersecurity frameworks, vulnerability alerts. SEC now requires cyber incident disclosure.
- **Sources**: CISA KEV JSON feed, NVD API
- **Priority**: MEDIUM -- increasingly relevant as cyber regulation accelerates

### State Regulators (NYDFS, CA DFPI)
- **Why**: State regulators often lead federal. BitLicense, Part 500 cyber, CCPA.
- **Sources**: All HTML scraping
- **Priority**: LOW unless state-level compliance is needed

### USTR (US Trade Representative)
- **Why**: Tariffs, trade agreements, export controls. Affects supply chain, semiconductors.
- **Sources**: Federal Register API (built)
- **Current status**: **Already fetching**

---

## Summary Matrix

| Agency | Already Fetching | API Quality | Impact | Add When |
|--------|:---:|:---:|:---:|---|
| SEC | Yes | Excellent | Critical | Already done |
| Fed | Partial | Excellent | Critical | Add speeches feed |
| CFPB | Partial | Excellent | High | Add complaints API |
| OCC | Partial | Good | High | Add enforcement search |
| FINRA | Yes | Scrape | High | Already done |
| FDIC | Partial | Good | High | Already via FR |
| CFTC | Partial | Good | High | Already via FR |
| OFAC | No | Good | Critical | **Do next** |
| EPA | Yes | Excellent | Medium | Already done |
| Basel/BIS | Yes | Scrape | High | Already done |
| Congress | No | Good | Medium | Soon |
| FDA | Yes | Excellent | Medium | Already done |
| EU | No | Complex | High (if EU) | Phase 2 |
| UK FCA | No | Scrape | Medium | Phase 2 |
| NIST/CISA | No | Excellent | Medium | Phase 2 |
| State | No | Scrape | Low | Phase 3 |

---

## Test Documents

See `test-documents.md` for concrete documents to test with from each agency.
