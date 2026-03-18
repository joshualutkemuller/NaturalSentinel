# Regulatory Regime Archetypes Reference Card

> **Skill:** `regime_detection` — `src/naturalsentinel/skills/regime_detection.py`
> **Branch:** `claude/expand-naturalsentinel-agents-j6oEQ`
> **Base:** `main` @ `0a51d23` (Merge PR #3 — financial desk agents)

---

## What Is a Regulatory Regime?

A **regulatory regime** is a macro-level state of the regulatory environment — a period characterised by a consistent direction of rulemaking, supervisory signalling, or enforcement emphasis across one or more agencies. Regimes differ from individual filings: a single rule is an *event*; a regime is a *sustained pattern* of events.

`regime_detection` identifies which regimes are **consistent with the language observed in current regulatory artifacts**. It informs — it does not prescribe firm-level actions.

---

## Regime Phases

Every active regime is assigned a phase based on signal density and cross-agency breadth:

| Phase | Meaning |
|-------|---------|
| **emergence** | First signals appearing; language confined to 1–2 agencies; not yet broad-based |
| **acceleration** | Growing filing volume and signal density; multiple agencies engaged |
| **peak** | Maximum breadth; most relevant agencies issuing on the topic simultaneously |
| **deceleration** | Implementation winding down; guidance clarifying edge cases; signal density falling |

---

## Detection Mechanism

Signal detection is two-pass:

1. **Keyword scoring (Pass 1 — no LLM cost):** For each filing in memory, term-frequency matching against the signal vocabulary below produces a `signal_strength` (0–1) per regime — the fraction of filings containing at least one signal term.

2. **LLM synthesis (Pass 2 — optional):** The scored signal table is passed to the LLM, which assigns phase labels, detects transitions (newly active / fading), and produces a macro-prudential narrative.

The `signal_threshold` parameter (default `0.10`) controls the minimum `signal_strength` needed for a regime to be reported as active rather than dormant.

---

## Regime Taxonomy

### 1 · Prudential Capital Tightening Cycle

**ID:** `prudential_capital_tightening`

Regulatory bodies are raising minimum capital requirements, constraining internal model optionality, or imposing new floors on standardised-approach calculations. Typical indicators: Basel IV output floor phase-in, GSIB surcharge recalibration, higher stress capital buffer (SCB), or reduced IRB optionality.

**Associated agencies:** BASEL, FED, OCC, FDIC

**Signal vocabulary:**

> output floor · standardised approach floor · IRB constraints · GSIB surcharge · stress capital buffer · SCB · higher capital · capital add-on · Pillar 2 add-on · RWA inflation · risk weight floor · model constraints · revised standardised approach · internal ratings-based · IRBA restrictions · leverage ratio buffer · Tier 1 capital · CET1 requirement · capital surcharge · conservation buffer · countercyclical buffer

---

### 2 · Supervisory Scrutiny Intensification

**ID:** `supervisory_scrutiny_intensification`

Supervisors are signalling elevated oversight expectations through increased MRA/MRIA issuance, horizontal examination themes, or explicit expectations guidance. Characterised by governance and risk management language rather than rulemaking. Often a leading indicator of enforcement actions or consent orders.

**Associated agencies:** FED, OCC, FDIC, CFPB

**Signal vocabulary:**

> matters requiring attention · MRA · matters requiring immediate attention · MRIA · horizontal review · supervisory expectations · exam findings · supervisory letter · heightened standards · safety and soundness · corporate governance · risk management expectations · model governance · third-party risk management · TPRM · board oversight · audit findings · deficiency letter · supervisory guidance · cease and desist

---

### 3 · Liquidity Stress Response Regime

**ID:** `liquidity_stress_response`

Regulators are responding to realised or anticipated liquidity stress by tightening HQLA eligibility, LCR / NSFR calibration, or contingency funding requirements. Typically follows bank failures or pronounced market dislocation. Often accompanied by data collection on uninsured deposit concentrations.

**Associated agencies:** FED, FDIC, OCC, BASEL

**Signal vocabulary:**

> HQLA · high-quality liquid assets · LCR · liquidity coverage ratio · NSFR · net stable funding ratio · uninsured deposits · concentrated funding · contingency funding plan · CFP · intraday liquidity · ILAAP · liquidity stress · funding concentration · FDIC insurance limit · liquidity risk management · Alt-M · alternative metric · runoff rate · stable funding · available stable funding

---

### 4 · Derivatives and Margin Reform Cycle

**ID:** `derivatives_margin_reform`

Central counterparty clearing mandates, uncleared margin rules, or SA-CCR recalibration are actively reshaping the derivatives exposure and collateral landscape. Phases follow BIS/IOSCO UMR implementation timelines or CFTC clearing mandate expansions. Key signals: initial margin thresholds, supervisory factor tables, netting eligibility.

**Associated agencies:** CFTC, FED, BASEL

**Signal vocabulary:**

> initial margin · IM requirements · SA-CCR · SIMM · ISDA SIMM · uncleared margin · UMR · phase-in · threshold amount · cleared derivatives · bilateral margin · variation margin · CCP margin · CEM replacement · current exposure method · alpha factor · supervisory factor · netting set · eligible collateral · segregation requirements

---

### 5 · Climate and ESG Integration Regime

**ID:** `climate_esg_integration`

Supervisors and standard-setters are embedding climate and ESG factors into prudential frameworks through stress testing scenarios, risk weight adjustments, or mandatory disclosure regimes. May precede formal rulemaking; often begins with voluntary guidance and data collection.

**Associated agencies:** FED, SEC, OCC, FDIC, BASEL

**Signal vocabulary:**

> climate risk · transition risk · physical risk · climate scenario · Scope 3 · green asset · sustainable finance · ESG · climate stress test · taxonomy · SFDR · TCFD · IFRS S2 · climate-related financial risk · stranded assets · net zero · carbon intensity · climate scenario analysis · Paris Agreement · greenwashing · sustainability disclosure · environmental risk

---

### 6 · Digital Asset Regulatory Capture Phase

**ID:** `digital_asset_regulatory_capture`

Regulators are establishing or clarifying frameworks for digital assets, crypto-asset custody, stablecoin issuance, or tokenised securities. Characterised by rapid, sometimes conflicting, guidance issuance across multiple agencies. Key accounting and custody signals: SAB 121/122, OCC interpretive letters on custody.

**Associated agencies:** SEC, CFTC, OCC, FED

**Signal vocabulary:**

> digital asset · crypto · stablecoin · cryptocurrency · virtual currency · SAB 121 · SAB 122 · custody of digital assets · tokenized · tokenised · distributed ledger · blockchain · DeFi · decentralised finance · crypto-asset · CBDC · central bank digital currency · digital wallet · spot bitcoin ETF · crypto exchange

---

### 7 · Resolution Planning and TLAC Tightening

**ID:** `resolution_tlac_tightening`

Regulators are raising gone-concern loss-absorbing capacity requirements, updating resolution planning expectations, or refining bail-in mechanics. Often accompanies systemic risk concerns or post-crisis reviews (e.g. SVB / CS failures). Signals typically appear in FED/FDIC living will feedback and TLAC issuance guidance.

**Associated agencies:** FED, FDIC, FSOC, BASEL

**Signal vocabulary:**

> TLAC · total loss-absorbing capacity · MREL · internal TLAC · resolution plan · living will · gone-concern · bail-in · recapitalisation · point of non-viability · PONV · resolution strategy · preferred resolution · SPOE · MPOE · issuance requirement · eligible instruments · resolution liquidity · resolution funding

---

### 8 · FRTB and Market Risk Model Implementation

**ID:** `frtb_model_implementation`

Internal model approach (IMA) approvals, expected shortfall recalibration, trading / banking book boundary reviews, or non-modellable risk factor (NMRF) treatments are actively being implemented or revised. Signals typically appear in Basel final standards and bank-specific IMA application guidance.

**Associated agencies:** BASEL, FED, OCC

**Signal vocabulary:**

> FRTB · Fundamental Review of the Trading Book · internal model approach · IMA · expected shortfall · P&L attribution · PLA test · trading book boundary · risk factor eligibility · NMRF · non-modellable risk factor · backtesting exceptions · sensitivities-based method · default risk charge · DRC · stressed expected shortfall · desk-level approval

---

### 9 · Agency and GSE Reform Cycle

**ID:** `agency_gse_reform`

FHFA is adjusting guarantee fee structures, credit risk transfer programmes, conforming loan limits, or conservatorship conditions for Fannie Mae / Freddie Mac. Signals changing economics for agency mortgage origination and securitisation. Enterprise capital rule developments are a key leading signal.

**Associated agencies:** FHFA

**Signal vocabulary:**

> conforming loan limit · CLL · g-fee · guarantee fee · credit risk transfer · CRT · GSE · government-sponsored enterprise · Fannie Mae · Freddie Mac · FHFA · conservatorship · enterprise capital · TBA market · agency MBS · prepayment · housing finance reform · single-family pricing

---

### 10 · Consumer Protection and Fair Lending Scrutiny

**ID:** `consumer_fair_lending_scrutiny`

Enforcement and supervisory focus is intensifying on consumer protection violations, fair lending, UDAAP, or discriminatory credit practices. Associated with CFPB examination cycles or DOJ referrals. Key signals are UDAAP enforcement actions, HMDA data publication, and CRA regulatory revisions.

**Associated agencies:** CFPB, OCC, FED, FDIC

**Signal vocabulary:**

> UDAP · UDAAP · unfair deceptive · fair lending · disparate impact · redlining · fair housing · ECOA · HMDA · CRA · community reinvestment · fair credit reporting · FCRA · consumer complaint · abusive act · prohibited basis · supervisory examination · enforcement action

---

### 11 · Platform Antitrust Enforcement Cycle

**ID:** `platform_antitrust_enforcement`

Antitrust authorities are intensifying scrutiny of large digital platforms through merger challenges, conduct investigations, or new obligations under the EU Digital Markets Act (DMA). Signals rising breakup risk, interoperability mandates, or gatekeeper designation.

**Associated agencies:** FTC, DOJ

**Signal vocabulary:**

> digital markets act · dma · gatekeeper · self-preferencing · interoperability · data portability · platform conduct · dominant position · merger challenge · hsr · second request · ftc complaint · doj antitrust · structural remedy · divestiture · vertical integration · app store · default agreements · platform neutrality · algorithmic fairness

---

### 12 · Data Privacy Regulatory Expansion

**ID:** `data_privacy_regulatory_expansion`

New or amended data privacy regimes are extending consent requirements, data subject rights, cross-border transfer restrictions, or enforcement authority simultaneously across jurisdictions.

**Associated agencies:** FTC, CISA

**Signal vocabulary:**

> gdpr · ccpa · cpra · data subject rights · right to erasure · consent requirement · data processing agreement · dpa · standard contractual clauses · scc · adequacy decision · cross-border transfer · data localisation · data residency · personal data · sensitive data · data broker · opt-out · privacy notice · legitimate interest · biometric data

---

### 13 · AI Governance and Accountability Regime

**ID:** `ai_governance_regulatory_cycle`

Regulators are establishing or tightening requirements for AI systems — covering risk classification, conformity assessments, transparency obligations, and bias audits. The EU AI Act is the primary legislative vector; FTC guidance and state-level algorithmic accountability laws are concurrent signals.

**Associated agencies:** FTC, SEC

**Signal vocabulary:**

> eu ai act · high-risk ai · ai system · conformity assessment · ai risk tier · foundation model · general purpose ai · algorithmic accountability · bias audit · ai transparency · explainability · ai governance · ai oversight · automated decision · profiling · ftc ai · ai liability · ai regulatory sandbox · responsible ai · ai impact assessment

---

### 14 · Cybersecurity Mandate Tightening Cycle

**ID:** `cybersecurity_mandate_tightening`

CISA, FCC, and SEC are expanding mandatory cybersecurity obligations through KEV patching directives, incident disclosure timelines (SEC Form 8-K), and FCC telecom network security rules. EO 14028 implementation is the key federal driver.

**Associated agencies:** CISA, FCC, SEC

**Signal vocabulary:**

> cisa kev · known exploited vulnerability · binding operational directive · bod · sec 8-k cybersecurity · incident disclosure · material breach · cybersecurity incident · zero day · patch deadline · eo 14028 · supply chain security · sbom · software bill of materials · critical infrastructure · network security · ransomware · vulnerability disclosure · fcc cyber · telecom security

---

### 15 · Spectrum Policy and Licensing Reform Cycle

**ID:** `spectrum_policy_reform`

The FCC is conducting spectrum auctions, reallocating mid-band or high-band frequencies, imposing new build-out obligations, or revising universal service fund contribution methodology. NTIA broadband funding programmes (BEAD) represent a concurrent signal.

**Associated agencies:** FCC, NTIA

**Signal vocabulary:**

> spectrum auction · fcc auction · c-band · cbrs · mid-band · mmwave · build-out obligation · coverage requirement · universal service fund · usf · e-rate · lifeline · ntia · bead · broadband equity · rural broadband · interference protection · dynamic spectrum sharing · spectrum licence · frequency allocation · tv white space

---

### 16 · Content Moderation and Platform Liability Shift

**ID:** `content_moderation_liability_shift`

Legislative or judicial changes are narrowing or redefining Section 230 liability protections, activating DSA very-large online platform (VLOP) obligations, or requiring algorithmic amplification disclosures.

**Associated agencies:** FTC, SEC

**Signal vocabulary:**

> section 230 · platform liability · dsa · digital services act · vlop · very large online platform · notice and takedown · ntd · content moderation · trusted flagger · algorithmic amplification · transparency report · crisis protocol · systemic risk · recommender system · illegal content · hate speech · csam · counter-terrorism · online safety · age verification

---

### 17 · Telecom Infrastructure Security Mandate

**ID:** `telecom_infrastructure_security`

FCC and NTIA are implementing supply chain security rules targeting equipment from designated foreign adversary vendors, imposing rip-and-replace obligations, and tightening roaming and interconnect security standards.

**Associated agencies:** FCC, CISA, NTIA

**Signal vocabulary:**

> rip and replace · huawei · zte · supply chain security · covered equipment · fcc covered list · calea · lawful intercept · roaming security · ss7 vulnerability · network slicing · open ran · trusted vendor · foreign adversary · banning order · reimbursement programme · network function virtualisation · telecom supply chain · subsea cable · landing station

---

### 18 · Data Residency and Cross-Border Data Regime

**ID:** `data_residency_localisation`

Governments are imposing or expanding data localisation requirements, invalidating existing cross-border transfer mechanisms, or enacting new data sovereignty frameworks. EU-US adequacy, China PIPL/DSL, and India DPDP Act are the principal vectors.

**Associated agencies:** FTC, CISA

**Signal vocabulary:**

> data localisation · data sovereignty · data residency · cross-border data transfer · eu-us data privacy framework · schrems · privacy shield · china pipl · dsl · data security law · india dpdp · digital personal data · government access · cloud act · fisa 702 · data border · mirror data · local storage requirement · data export restriction · third country transfer

---

## Quick-Reference Table

### Financial Services Regimes

| ID | Label | Key Agencies | Primary Signal Terms |
|----|-------|-------------|---------------------|
| `prudential_capital_tightening` | Prudential Capital Tightening | BASEL, FED, OCC, FDIC | output floor, GSIB surcharge, CET1 |
| `supervisory_scrutiny_intensification` | Supervisory Scrutiny | FED, OCC, FDIC, CFPB | MRA, MRIA, horizontal review |
| `liquidity_stress_response` | Liquidity Stress Response | FED, FDIC, OCC, BASEL | HQLA, LCR, NSFR, uninsured deposits |
| `derivatives_margin_reform` | Derivatives & Margin Reform | CFTC, FED, BASEL | SA-CCR, SIMM, UMR, initial margin |
| `climate_esg_integration` | Climate / ESG Integration | FED, SEC, OCC, FDIC | transition risk, TCFD, climate scenario |
| `digital_asset_regulatory_capture` | Digital Asset Capture | SEC, CFTC, OCC, FED | stablecoin, SAB 121/122, DeFi |
| `resolution_tlac_tightening` | Resolution / TLAC Tightening | FED, FDIC, FSOC, BASEL | TLAC, bail-in, living will, MREL |
| `frtb_model_implementation` | FRTB / Market Risk Models | BASEL, FED, OCC | FRTB, IMA, expected shortfall, NMRF |
| `agency_gse_reform` | Agency / GSE Reform | FHFA | g-fee, CRT, conforming limit, TBA |
| `consumer_fair_lending_scrutiny` | Consumer / Fair Lending | CFPB, OCC, FED, FDIC | UDAAP, redlining, HMDA, ECOA |

### Technology & Telecom Regimes

| ID | Label | Key Agencies | Primary Signal Terms |
|----|-------|-------------|---------------------|
| `platform_antitrust_enforcement` | Platform Antitrust Enforcement | FTC, DOJ | DMA, gatekeeper, self-preferencing |
| `data_privacy_regulatory_expansion` | Data Privacy Expansion | FTC, CISA | GDPR, CCPA, adequacy, SCC |
| `ai_governance_regulatory_cycle` | AI Governance | FTC, SEC | EU AI Act, high-risk AI, bias audit |
| `cybersecurity_mandate_tightening` | Cybersecurity Mandates | CISA, FCC, SEC | KEV, incident disclosure, EO 14028 |
| `spectrum_policy_reform` | Spectrum Policy Reform | FCC, NTIA | spectrum auction, build-out, USF |
| `content_moderation_liability_shift` | Content Moderation Liability | FTC, SEC | Section 230, VLOP, DSA, NTD |
| `telecom_infrastructure_security` | Telecom Infrastructure Security | FCC, CISA, NTIA | rip-replace, Huawei, CALEA |
| `data_residency_localisation` | Data Residency / Localisation | FTC, CISA | data localisation, PIPL, DPDP, SCCs |

---

## Extending the Taxonomy

To add a new regime archetype, append an entry to `REGIME_ARCHETYPES` in `src/naturalsentinel/skills/regime_detection.py`:

```python
{
    "id": "your_regime_id",           # snake_case unique identifier
    "label": "Human-Readable Label",
    "description": (
        "One or two sentences describing what this regime represents "
        "and what conditions typically give rise to it."
    ),
    "signal_terms": [
        "term one",                    # lower-case; word-boundary matched
        "term two",
        # ...
    ],
    "domains": ["FED", "OCC"],         # subset of DOMAIN_BUSINESS_LINES keys (upper-case)
}
```

No other code changes are needed — the skill's keyword scoring and LLM synthesis loops iterate over `REGIME_ARCHETYPES` dynamically.

---

*Source: `src/naturalsentinel/skills/regime_detection.py` · `REGIME_ARCHETYPES` list*
