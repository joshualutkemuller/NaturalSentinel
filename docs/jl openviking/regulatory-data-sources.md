# Regulatory Data Sources for OpenViking

Brainstorm of what regulatory bodies, data sources, and APIs to feed into
OpenViking, organized by what we have, what we should add, and why.

---

## Current State

### Live Fetchers (already built)

| Source | API / Method | Domains Covered | Notes |
|--------|-------------|-----------------|-------|
| **Federal Register** | JSON API (`federalregister.gov/api/v1`) | FED, CFPB, OCC, FDIC, CFTC, SEC, EPA, USTR, FHFA, FDA | Primary source for all US rulemaking. Structured, reliable, free, no auth. |
| **SEC EDGAR** | EFTS search (`efts.sec.gov/LATEST`) | SEC | Supplements FR with enforcement orders, no-action letters, staff guidance, interpretive releases |
| **BIS/BCBS** | HTML scrape (`bis.org/bcbs/publications.htm`) | BASEL | No JSON API. Publishes infrequently (~monthly). Use 90-day window. |
| **FINRA** | HTML scrape (`finra.org/rules-guidance/notices`) | FINRA | No JSON API. Regulatory notices for broker-dealers. |

### Current `RegulatoryDomain` Enum

SEC, CFPB, FED, FDA, EPA, USTR, FHFA, OCC, FINRA, CFTC, FDIC, BASEL

---

## Tier 1 -- Add These First (high value, good APIs)

These are agencies with **structured, free, no-auth APIs** that cover major
blind spots in the current monitor.

### CFPB Complaint Database

- **What**: Consumer complaints about financial products (credit cards, mortgages, etc.)
- **API**: `https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/`
- **Format**: JSON, fully structured, supports date-range and product filtering
- **Why**: Complaint volume spikes are leading indicators of enforcement actions. If complaints about "debt collection" triple in a quarter, an enforcement action usually follows. Feed complaint trend data into OV as `viking://resources/regulatory/cfpb/complaints/` and let the LLM correlate with CFPB proposed rules.
- **Frequency**: Weekly poll
- **Domain**: `cfpb`

### SEC XBRL / Inline XBRL Filings

- **What**: Structured financial data from company filings (10-K, 10-Q, 8-K)
- **API**: `https://data.sec.gov/api/xbrl/companyfacts/` and `https://data.sec.gov/submissions/`
- **Format**: JSON
- **Why**: When SEC proposes a rule change (e.g., climate disclosure), you want to know which companies are affected and how. XBRL data gives you the "who" to pair with the regulatory "what." Ingest company facts as OV entities under `viking://resources/entities/companies/`.
- **Frequency**: On-demand (when a relevant SEC rule is detected)
- **Domain**: `sec`

### Congressional Bills & Reports (Congress.gov)

- **What**: Bills, amendments, committee reports that often precede regulation
- **API**: `https://api.congress.gov/v3/` (free, API key required)
- **Format**: JSON
- **Why**: Legislation is the upstream signal. A bill that passes committee is a strong indicator of future rulemaking. "The EARN IT Act passed Senate Judiciary" means "prepare for new content moderation rules." Track bills tagged with financial, environmental, health, trade committees.
- **Frequency**: Weekly poll for bills in active committees
- **Domain**: New -- `CONGRESS` or tag as cross-domain

### Federal Reserve Economic Data (FRED)

- **What**: Economic time series -- interest rates, CPI, unemployment, M2
- **API**: `https://api.stlouisfed.org/fred/series/observations` (free, API key)
- **Format**: JSON
- **Why**: Macroeconomic context for regulatory impact. A proposed capital rule during a rate hike cycle is different from one during easing. Ingest key series as OV resources under `viking://resources/macro/` and let `BuildContextSkill` pull them in.
- **Frequency**: Monthly (aligned with data release schedule)
- **Domain**: `fed` (enrichment, not a regulatory source per se)

### Treasury / OFAC Sanctions

- **What**: Specially Designated Nationals (SDN) list, sanctions programs
- **API**: `https://sanctionssearch.ofac.treas.gov/` + bulk CSV downloads at `https://www.treasury.gov/ofac/downloads/`
- **Format**: XML/CSV (SDN list), JSON via search API
- **Why**: Sanctions compliance is a first-order concern. New SDN additions affect banking, trade finance, payments. Every OFAC update should trigger a scan and land in OV.
- **Frequency**: Daily (OFAC updates the SDN list daily)
- **Domain**: New -- `OFAC` or `TREASURY`

---

## Tier 2 -- Add Next (high value, requires scraping or auth)

These are important but either have no structured API or require registration.

### CFTC Commitments of Traders (COT)

- **What**: Weekly positions data for futures/options markets
- **API**: Bulk download at `https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm`
- **Format**: CSV/Excel
- **Why**: Position concentration data provides context for derivatives regulation. When the CFTC proposes position limits, COT data tells you who's affected.
- **Frequency**: Weekly (released every Friday)
- **Domain**: `cftc`

### OCC Enforcement Actions

- **What**: Consent orders, cease-and-desist, civil money penalties against banks
- **API**: HTML scrape at `https://apps.occ.gov/EASearch/`
- **Format**: HTML listing + PDF documents
- **Why**: Enforcement actions reveal what the OCC actually cares about (as opposed to what they say in guidance). Patterns in enforcement predict future rulemaking.
- **Frequency**: Monthly
- **Domain**: `occ`

### EU Official Journal (EUR-Lex)

- **What**: EU regulations, directives, decisions
- **API**: `https://eur-lex.europa.eu/api/` (SPARQL endpoint + REST)
- **Format**: XML/RDF/HTML
- **Why**: EU regulation has extraterritorial impact. GDPR, MiCA (crypto), AI Act, DORA (digital resilience) all affect US firms with EU exposure. This is the biggest international gap.
- **Frequency**: Weekly
- **Domain**: New -- `EU` (covers ECB, ESMA, EBA, EIOPA collectively)

### UK FCA / PRA

- **What**: Financial Conduct Authority and Prudential Regulation Authority publications
- **API**: No structured API. Scrape `https://www.fca.org.uk/publications` and `https://www.bankofengland.co.uk/prudential-regulation/publication`
- **Format**: HTML + PDF
- **Why**: Post-Brexit UK divergence from EU rules creates compliance complexity for global banks. FCA enforcement is aggressive and often first-mover on fintech/crypto.
- **Frequency**: Weekly
- **Domain**: New -- `FCA` or `UK`

### NIST Cybersecurity Framework / CISA Advisories

- **What**: Cybersecurity standards, vulnerability alerts, binding operational directives
- **API**: CISA has a structured feed at `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` and NVD API at `https://services.nvd.nist.gov/rest/json/cves/2.0`
- **Format**: JSON
- **Why**: Cyber regulation is accelerating (SEC cyber disclosure rules, NYDFS Part 500, DORA). Pairing vulnerability data with regulatory requirements is powerful -- "this CVE affects systems in scope for SEC's new incident reporting rule."
- **Frequency**: Daily (CISA KEV), weekly (NIST frameworks)
- **Domain**: New -- `CYBER` or enrich existing domains

### State-Level Regulators (NYDFS, CA DFPI, TX DOB)

- **What**: State banking/financial regulation. NYDFS Part 500 (cyber), CA DFPI enforcement, TX DOB bulletins.
- **API**: No structured APIs. All are HTML scrape.
- **Format**: HTML + PDF
- **Why**: State regulators often lead federal. NYDFS crypto licensing (BitLicense) preceded SEC. CA privacy (CCPA/CPRA) preceded federal attempts. State actions preview federal direction.
- **Frequency**: Monthly
- **Domain**: New -- `STATE` with sub-tags per state

---

## Tier 3 -- Enrichment Sources (context, not regulation)

These aren't regulatory filings themselves but provide critical context for
impact analysis.

### Court Decisions (PACER / CourtListener)

- **What**: Federal court rulings on regulatory challenges
- **API**: CourtListener API at `https://www.courtlistener.com/api/rest/v4/` (free, API key)
- **Format**: JSON
- **Why**: Courts can vacate rules (Chevron overturned!). A pending legal challenge to an SEC rule changes its impact assessment entirely. Track cases that reference specific CFR parts.
- **Frequency**: Weekly
- **Use**: Enrich impact assessments with litigation risk

### Trade Association Comment Letters

- **What**: Industry group comments on proposed rules (SIFMA, ABA, ICI, ISDA)
- **API**: Regulations.gov API at `https://api.regulations.gov/v4/` (free, API key required)
- **Format**: JSON
- **Why**: Comment letters reveal industry's actual concerns. If SIFMA's comment on a margin rule says "this will cost $2B to implement," that's material context. Also tracks which rules are most contested.
- **Frequency**: Weekly, keyed to open comment periods
- **Use**: Feed into OV alongside the proposed rule they reference

### Federal Reserve Speeches / Testimony

- **What**: Fed governor speeches, congressional testimony, press conferences
- **API**: `https://www.federalreserve.gov/json/ne-speeches.json`
- **Format**: JSON listing + HTML full text
- **Why**: Forward guidance. When a Fed governor says "we're examining whether Basel III endgame needs recalibration," that's a signal months before a formal notice. These are leading indicators.
- **Frequency**: Real-time (RSS) or daily poll
- **Use**: Enrich `fed` domain analysis

### IMF / World Bank Policy Papers

- **What**: Global financial stability reports, policy papers
- **API**: IMF data API at `https://www.imf.org/external/datamapper/api/v1/`
- **Format**: JSON
- **Why**: International context for Basel/BCBS analysis. When IMF flags "emerging market debt risks," that informs Basel capital rule interpretations.
- **Frequency**: Quarterly
- **Use**: Enrich `basel` domain

---

## Recommended Fetch Schedule

| Frequency | Sources | Rationale |
|-----------|---------|-----------|
| **Real-time / Daily** | OFAC SDN, CISA KEV, Fed speeches RSS | Time-sensitive -- sanctions and vulnerabilities need immediate awareness |
| **Weekly** | Federal Register, EDGAR, CFPB complaints, Congress.gov, Regulations.gov comments, CourtListener, EU OJ, FCA/PRA | Core regulatory pipeline -- weekly is the right cadence for proposed/final rules |
| **Biweekly** | FINRA notices, OCC enforcement, CFTC COT, NIST frameworks | These publish less frequently, biweekly catches everything without wasted calls |
| **Monthly** | BIS/BCBS, state regulators, IMF/World Bank | Slow-publishing sources. BIS is quarterly; monthly polls are sufficient. |
| **On-demand** | SEC XBRL (company facts), FRED (economic series) | Triggered by relevant rule detection, not on a schedule |

---

## OpenViking Filesystem Layout for Ingested Sources

```
viking://resources/regulatory/
├── sec/
│   ├── filings/          # Federal Register + EDGAR filings
│   ├── enforcement/      # EDGAR enforcement actions
│   └── xbrl/             # Company facts (on-demand)
├── cfpb/
│   ├── filings/          # Federal Register filings
│   └── complaints/       # CFPB complaint trends
├── fed/
│   ├── filings/          # Federal Register filings
│   ├── speeches/         # Governor speeches / testimony
│   └── fred/             # Key economic series
├── cftc/
│   ├── filings/          # Federal Register filings
│   └── cot/              # Commitments of traders
├── occ/
│   ├── filings/          # Federal Register filings
│   └── enforcement/      # Consent orders, CMPs
├── finra/
│   └── notices/          # Regulatory notices
├── basel/
│   └── publications/     # BIS/BCBS standards & consultative docs
├── treasury/
│   └── ofac/             # SDN list updates
├── congress/
│   ├── bills/            # Active legislation
│   └── committee-reports/
├── eu/
│   ├── regulations/      # EUR-Lex
│   └── directives/
├── uk/
│   ├── fca/              # FCA publications
│   └── pra/              # PRA publications
├── cyber/
│   ├── cisa/             # KEV + advisories
│   └── nist/             # Framework updates
└── state/
    ├── nydfs/
    ├── ca-dfpi/
    └── tx-dob/

viking://resources/context/
├── comments/             # Regulations.gov comment letters
├── court-decisions/      # CourtListener rulings
├── macro/                # FRED economic series
└── international/        # IMF / World Bank policy papers
```

---

## New `RegulatoryDomain` Enum Values to Add

```python
class RegulatoryDomain(Enum):
    # existing
    SEC = "sec"
    CFPB = "cfpb"
    FED = "fed"
    FDA = "fda"
    EPA = "epa"
    USTR = "ustr"
    FHFA = "fhfa"
    OCC = "occ"
    FINRA = "finra"
    CFTC = "cftc"
    FDIC = "fdic"
    BASEL = "basel"
    # new -- Tier 1
    OFAC = "ofac"        # Treasury / OFAC sanctions
    CONGRESS = "congress" # Congressional bills
    # new -- Tier 2
    EU = "eu"            # EUR-Lex (ESMA, EBA, ECB, EIOPA)
    FCA = "fca"          # UK Financial Conduct Authority
    NIST = "nist"        # NIST / CISA cybersecurity
    NYDFS = "nydfs"      # New York Dept of Financial Services
```

---

## Priority Matrix

| Source | Effort | Value | API Quality | Recommendation |
|--------|--------|-------|-------------|----------------|
| CFPB Complaints | Low | High | Excellent JSON API | **Do first** -- 1 day, huge signal |
| Congress.gov | Low | High | Good JSON API (key required) | **Do first** -- 1 day, upstream signal |
| OFAC SDN | Medium | Critical | CSV/XML bulk + search | **Do first** -- 2 days, compliance-critical |
| Regulations.gov | Low | High | Good JSON API (key required) | **Do second** -- 1 day, context enrichment |
| FRED | Low | Medium | Excellent JSON API | **Do second** -- 1 day, macro context |
| Fed Speeches | Low | High | JSON listing | **Do second** -- 1 day, forward guidance |
| CFTC COT | Medium | Medium | CSV bulk download | **Do third** -- parsing effort |
| OCC Enforcement | Medium | High | HTML scrape | **Do third** -- valuable but scraping |
| EUR-Lex | High | High | Complex SPARQL/REST | **Do third** -- big lift, big payoff |
| UK FCA/PRA | High | Medium | HTML scrape | **Phase 2** -- depends on international scope |
| NIST/CISA | Low | Medium | Good JSON API | **Phase 2** -- if cyber regulation is in scope |
| State regulators | High | Medium | All scraping | **Phase 2** -- only if state-level needed |
| CourtListener | Low | High | Good JSON API | **Phase 2** -- enrichment layer |
| IMF/World Bank | Low | Low | JSON API | **Phase 3** -- nice to have |
