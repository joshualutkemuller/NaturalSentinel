"""Sample regulatory filings and pre-built mock analyses for demos/tests."""

SAMPLE_FILINGS: list[dict] = [
    {
        "id": "SEC-2026-0312-A",
        "title": "Amendments to Regulation S-K: Climate-Related Disclosures",
        "domain": "sec",
        "source_url": "https://www.sec.gov/rules/proposed/2026/33-11275.htm",
        "published_date": "2026-03-10",
        "change_type": "final_rule",
        "raw_text": (
            "The Securities and Exchange Commission is adopting amendments to Regulation S-K "
            "and Regulation S-X to require registrants to provide certain climate-related "
            "information in their registration statements and annual reports. The final rules "
            "will require disclosure of material climate-related risks, greenhouse gas emissions "
            "(Scope 1, Scope 2, and for larger accelerated filers, Scope 3), transition plans, "
            "governance processes for climate oversight, and financial statement footnotes on "
            "climate impacts. Compliance is phased: Large Accelerated Filers must begin "
            "reporting in fiscal years beginning after December 15, 2026; Accelerated Filers "
            "after December 15, 2027; and Smaller Reporting Companies after December 15, 2028. "
            "Non-compliance may result in enforcement actions, comment letters, and potential "
            "delisting referrals."
        ),
    },
    {
        "id": "CFPB-2026-0228-B",
        "title": "Updated Supervisory Guidance on AI-Driven Credit Decisioning",
        "domain": "cfpb",
        "source_url": "https://www.consumerfinance.gov/rules-policy/notice-2026-02/",
        "published_date": "2026-02-28",
        "change_type": "guidance",
        "raw_text": (
            "The Consumer Financial Protection Bureau issues updated supervisory guidance "
            "clarifying that creditors using artificial intelligence or machine learning models "
            "in credit underwriting must provide specific and accurate adverse action notices "
            "under the Equal Credit Opportunity Act and Fair Credit Reporting Act. The Bureau "
            "expects that creditors will not rely on opaque or unexplainable model outputs. "
            "Creditors must demonstrate model validation, bias testing across protected classes, "
            "and ongoing monitoring with at least quarterly re-validation. Institutions with "
            "assets exceeding $10 billion are subject to immediate supervisory examination. "
            "Smaller institutions have 18 months to demonstrate compliance."
        ),
    },
    {
        "id": "FED-2026-0305-C",
        "title": "Enhanced Prudential Standards for Crypto-Asset Custody by Banking Organizations",
        "domain": "fed",
        "source_url": "https://www.federalreserve.gov/newsevents/pressreleases/bcreg20260305a.htm",
        "published_date": "2026-03-05",
        "change_type": "proposed_rule",
        "raw_text": (
            "The Board of Governors of the Federal Reserve System proposes enhanced prudential "
            "standards for state member banks and bank holding companies engaging in custody "
            "of crypto-assets. The proposed rule would require (1) segregation of customer "
            "crypto-assets from proprietary holdings, (2) capital charges reflecting the "
            "volatility of custodied assets using a modified Basel III framework, (3) quarterly "
            "stress testing of operational and cybersecurity resilience, and (4) board-level "
            "risk governance attestations. Comments are due within 90 days of Federal Register "
            "publication. The Board estimates compliance costs of $2-5 million for mid-size "
            "institutions."
        ),
    },
    {
        "id": "FDA-2026-0301-D",
        "title": "Draft Guidance on Predetermined Change Control Plans for AI/ML-Enabled Medical Devices",
        "domain": "fda",
        "source_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/2026-ai-ml-pccp",
        "published_date": "2026-03-01",
        "change_type": "guidance",
        "raw_text": (
            "The Food and Drug Administration issues draft guidance describing recommendations "
            "for Predetermined Change Control Plans (PCCPs) that manufacturers of AI/ML-enabled "
            "medical devices may include in premarket submissions. The PCCP framework allows "
            "manufacturers to describe planned modifications and the methodology for implementing "
            "those modifications without requiring new premarket submissions for each change. "
            "Manufacturers must specify (a) the description of planned modifications, (b) the "
            "modification protocol including validation and performance testing, and (c) the "
            "impact assessment methodology. This guidance applies to Software as a Medical "
            "Device (SaMD) classified as Class II or Class III. Comments are requested within "
            "60 days."
        ),
    },
    {
        "id": "EPA-2026-0215-E",
        "title": "Revised National Ambient Air Quality Standards for Particulate Matter (PM2.5)",
        "domain": "epa",
        "source_url": "https://www.epa.gov/naaqs/pm-naaqs-2026-revision",
        "published_date": "2026-02-15",
        "change_type": "final_rule",
        "raw_text": (
            "The Environmental Protection Agency finalizes revisions to the National Ambient "
            "Air Quality Standards for fine particulate matter (PM2.5), lowering the annual "
            "standard from 9.0 micrograms per cubic meter to 8.0 micrograms per cubic meter. "
            "The 24-hour standard remains at 35 micrograms per cubic meter. States must submit "
            "revised State Implementation Plans within 24 months. Non-attainment areas will be "
            "redesignated, potentially affecting industrial permitting for manufacturing, power "
            "generation, and transportation sectors. The EPA estimates the rule will prevent "
            "4,200 premature deaths annually. Affected industries should anticipate stricter "
            "Title V permit conditions and potential increases in emissions offset requirements."
        ),
    },
    # ── Securities finance & lending filings ────────────────────────────────
    {
        "id": "FHFA-2026-0310-G",
        "title": "2026 Conforming Loan Limit Adjustment and Updated Single-Family Selling Guide",
        "domain": "fhfa",
        "source_url": "https://www.fhfa.gov/SupervisionRegulation/Rules/Pages/2026-conforming-limits.aspx",
        "published_date": "2026-03-10",
        "change_type": "notice",
        "raw_text": (
            "The Federal Housing Finance Agency announces the 2026 conforming loan limits for "
            "Fannie Mae and Freddie Mac. The baseline conforming loan limit for one-unit "
            "properties is increased from $766,550 to $806,500, reflecting the 5.2% increase "
            "in average U.S. home values. High-cost area limits increase proportionally to "
            "$1,209,750. Additionally, the FHFA is updating the Selling Guide to revise "
            "acceptable collateral haircut schedules for Agency MBS pledged in securities "
            "lending transactions. The updated haircut matrix reflects current duration risk "
            "and prepayment volatility. Effective for all deliveries on or after May 1, 2026. "
            "GSE counterparties must update their collateral eligibility systems and re-price "
            "existing TBA forward commitments that fall near the new limit threshold. "
            "Credit Risk Transfer (CRT) program parameters remain unchanged for this cycle."
        ),
    },
    {
        "id": "OCC-2026-0308-H",
        "title": "Revised Interagency Guidance on Leveraged Lending Underwriting Standards",
        "domain": "occ",
        "source_url": "https://www.occ.gov/news-issuances/bulletins/2026/bulletin-2026-12.html",
        "published_date": "2026-03-08",
        "change_type": "guidance",
        "raw_text": (
            "The Office of the Comptroller of the Currency, jointly with the Federal Reserve "
            "and FDIC, issues revised interagency guidance on leveraged lending underwriting "
            "standards. The guidance reduces the maximum total debt-to-EBITDA threshold "
            "considered reasonable from 6.0x to 5.5x for most industries, with sector-specific "
            "carve-outs for infrastructure and healthcare. The guidance also tightens "
            "definitions of leveraged lending to include all facilities where the borrower's "
            "total debt exceeds 4.0x EBITDA regardless of credit rating. Banks must maintain "
            "meaningful lender protections including financial maintenance covenants in at least "
            "50% of new leveraged loan facilities. Institutions with leveraged loan portfolios "
            "exceeding 3x Tier 1 capital are subject to enhanced supervisory review. "
            "Compliance expected within 180 days of publication."
        ),
    },
    {
        "id": "FINRA-2026-0305-I",
        "title": "Amendments to FINRA Rule 4210: Margin Requirements for TBA and Specified Pool Transactions",
        "domain": "finra",
        "source_url": "https://www.finra.org/rules-guidance/notices/26-07",
        "published_date": "2026-03-05",
        "change_type": "final_rule",
        "raw_text": (
            "FINRA adopts amendments to Rule 4210 (Margin Requirements) to establish "
            "mandatory margin requirements for to-be-announced (TBA) transactions, specified "
            "pool transactions, and net interest margin (NIM) securities. Effective August 1, "
            "2026, members must collect variation margin daily on TBA net positions exceeding "
            "$10 million notional, and initial margin on positions exceeding $50 million "
            "notional using the schedule-based or model-based approach. The final rule exempts "
            "transactions cleared through a registered clearing agency. Prime brokers providing "
            "financing for agency MBS must integrate these requirements into existing customer "
            "margin account calculations. Firms must update margin methodology documentation, "
            "stress testing scenarios, and customer agreement templates. The estimated "
            "industry-wide margin mobilization requirement is $12-18 billion."
        ),
    },
    {
        "id": "CFTC-2026-0301-J",
        "title": "Uncleared Margin Rules Phase 6 Implementation and SIMM Recalibration",
        "domain": "cftc",
        "source_url": "https://www.cftc.gov/PressRoom/PressReleases/2026-041",
        "published_date": "2026-03-01",
        "change_type": "final_rule",
        "raw_text": (
            "The Commodity Futures Trading Commission finalizes guidance on the Phase 6 "
            "implementation of Uncleared Margin Rules (UMR) and adopts the ISDA SIMM v2.7 "
            "recalibration effective September 1, 2026. The recalibration reflects updated "
            "historical stress periods including 2022-2023 rate volatility, increasing "
            "initial margin requirements for interest rate and credit derivatives by an "
            "estimated 8-15%. The CFTC also adopts amendments to 17 CFR Part 23 requiring "
            "covered swap entities to maintain an Aggregate Notional Amount (ANA) threshold "
            "documentation framework with quarterly recertification. Cross-currency swap "
            "delta sensitivities under the standardized schedule are revised. Entities near "
            "the $50 billion ANA threshold must implement daily ANA monitoring. "
            "The rule affects initial margin models, custodial arrangements with third-party "
            "segregation providers, and MVA hedging strategies."
        ),
    },
    {
        "id": "FDIC-2026-0225-K",
        "title": "Final Rule: Large Bank Surcharge and Revised Deposit Insurance Assessment Rates",
        "domain": "fdic",
        "source_url": "https://www.fdic.gov/news/press-releases/2026/pr26022.html",
        "published_date": "2026-02-25",
        "change_type": "final_rule",
        "raw_text": (
            "The Federal Deposit Insurance Corporation adopts a final rule imposing a special "
            "assessment surcharge on insured depository institutions with total assets exceeding "
            "$50 billion, to rebuild the Deposit Insurance Fund following 2023 bank failures. "
            "The surcharge is calculated at 13.4 basis points annually on uninsured deposits "
            "exceeding $5 billion. The assessment applies quarterly beginning Q2 2026. "
            "Simultaneously, the FDIC revises the deposit insurance assessment rate schedule "
            "under 12 CFR Part 327, increasing the initial base assessment rate range from "
            "2.5-32 bps to 3.0-40 bps for large institutions. Brokered deposits will receive "
            "a 50% higher weighting in the assessment rate calculation. Institutions must "
            "update their deposit funding cost models and reassess the economics of brokered "
            "deposit programs. The FDIC estimates aggregate industry cost of $15.8 billion."
        ),
    },
    {
        "id": "BASEL-2026-0315-L",
        "title": "Basel IV: Output Floor Phase-In Schedule and Revised Credit RWA Methodology",
        "domain": "basel",
        "source_url": "https://www.bis.org/bcbs/publ/d572.htm",
        "published_date": "2026-03-15",
        "change_type": "final_rule",
        "raw_text": (
            "The Basel Committee on Banking Supervision confirms the phase-in schedule for "
            "the Basel IV output floor under the finalised Basel III reforms. The output floor "
            "requires that internal model RWA may not fall below 72.5% of standardised approach "
            "RWA, phasing in from 50% in 2025 to 72.5% by 2028. The Committee also publishes "
            "revised credit risk standardised approach (SA-CR) risk weights for repo-style "
            "transactions and securities financing transactions, lowering the applicable risk "
            "weight for investment-grade collateralised lending from 75% to 65% where robust "
            "daily margining is demonstrated. The revised SA-CCR framework for derivatives "
            "introduces updated supervisory factors for interest rate options. Banks using "
            "advanced IRBA models for secured lending must begin parallel runs comparing "
            "output floor results by Q3 2026. Capital optimisation desks should model the "
            "constraint binding scenarios under multiple output floor trajectories."
        ),
    },
    {
        "id": "FED-2026-0312-M",
        "title": "CCAR 2026: Supervisory Stress Test Scenarios and Exploratory Market Shock",
        "domain": "fed",
        "source_url": "https://www.federalreserve.gov/publications/2026-supervisory-scenarios.htm",
        "published_date": "2026-03-12",
        "change_type": "notice",
        "raw_text": (
            "The Federal Reserve releases the 2026 supervisory stress test scenarios under "
            "the Comprehensive Capital Analysis and Review (CCAR). The severely adverse scenario "
            "features: a 500 bps increase in the BBB corporate spread (vs 390 bps in 2025), "
            "10-year Treasury yields declining to 0.75%, S&P 500 falling 55% peak-to-trough, "
            "unemployment rising to 10.0%, and a 35% decline in commercial real estate prices. "
            "An exploratory market shock component adds a simultaneous 200 bps parallel shift "
            "in the yield curve combined with acute liquidity stress in repo markets, with "
            "general collateral repo rates spiking 300 bps above fed funds for a 30-day window. "
            "The exploratory scenario specifically stresses securities financing books, prime "
            "brokerage, and leveraged lending portfolios. Firms must submit capital plans by "
            "April 5, 2026. Results will be published in June 2026."
        ),
    },
    {
        "id": "FED-2026-0303-N",
        "title": "Supervisory Guidance SR 11-7 Update: Model Risk Management for AI/ML and Optimization Models",
        "domain": "fed",
        "source_url": "https://www.federalreserve.gov/supervisionreg/srletters/sr2603.htm",
        "published_date": "2026-03-03",
        "change_type": "guidance",
        "raw_text": (
            "The Federal Reserve and OCC issue an update to Supervisory Guidance SR 11-7 "
            "to address model risk management expectations for artificial intelligence, machine "
            "learning, and optimization models used in financial decision-making. The guidance "
            "clarifies that all quantitative models used in capital allocation, portfolio "
            "optimization, pricing, and risk management are subject to SR 11-7 regardless of "
            "whether they use traditional statistical or AI/ML methodologies. Key additions "
            "include: (1) optimizer models used for balance sheet management and capital "
            "allocation require Tier 1 validation with annual full re-validation, (2) "
            "reinforcement learning and online learning models must maintain a formal concept "
            "drift monitoring framework with predefined retraining triggers, (3) challenger "
            "models must be maintained for all production optimization models, and (4) model "
            "inventories must be updated to include all optimization and allocation algorithms. "
            "Examiners will begin assessing AI/ML model governance in Q3 2026 examinations."
        ),
    },
    {
        "id": "SEC-2026-0295-O",
        "title": "Amendments to Rule 15c3-3: Customer Protection for Securities Lending Collateral",
        "domain": "sec",
        "source_url": "https://www.sec.gov/rules/final/2026/34-98754.htm",
        "published_date": "2026-02-25",
        "change_type": "final_rule",
        "raw_text": (
            "The Securities and Exchange Commission adopts amendments to Rule 15c3-3 "
            "(Customer Protection Rule) to address collateral management practices in "
            "securities lending transactions. The amendments require broker-dealers to "
            "maintain a minimum 102% collateral coverage ratio (increased from 100%) for "
            "customer securities on loan, with daily mark-to-market and same-day margin calls "
            "for any shortfall exceeding 0.5% of loan value. Eligible non-cash collateral "
            "is restricted: equities may not exceed 30% of total collateral for any single "
            "counterparty (reduced from 40%), and the rule eliminates the use of non-HQLA "
            "fixed income securities as collateral for customer loans. Broker-dealers must "
            "implement a formal collateral substitution process with customer consent for "
            "material collateral composition changes. Rehypothecation of customer collateral "
            "is limited to 140% of the customer's net debit balance. Compliance required "
            "within 270 days of publication."
        ),
    },
    {
        "id": "CFTC-2026-0310-P",
        "title": "SA-CCR Implementation Guidance: Supervisory Factors for Repo and Securities Financing",
        "domain": "cftc",
        "source_url": "https://www.cftc.gov/PressRoom/PressReleases/2026-054",
        "published_date": "2026-03-10",
        "change_type": "guidance",
        "raw_text": (
            "The Commodity Futures Trading Commission issues supplemental implementation "
            "guidance on the Standardised Approach for Counterparty Credit Risk (SA-CCR) "
            "as it applies to repo, reverse repo, and securities financing transactions "
            "executed by swap dealers and major swap participants. The guidance clarifies "
            "that repo-style transactions with a remaining maturity under 10 business days "
            "qualify for the 0% supervisory factor when subject to daily margining, consistent "
            "with the Basel Committee's interpretation. For transactions involving "
            "non-investment-grade collateral, the supervisory factor is revised to 2.0% "
            "(from 1.5%). The guidance also addresses the treatment of netting sets combining "
            "repo and OTC derivative positions for swap dealers operating prime brokerage "
            "businesses. Firms must submit updated SA-CCR calculation methodologies to their "
            "lead supervisor by June 30, 2026. This guidance affects EAD calculations for "
            "capital adequacy, counterparty credit risk limits, and XVA pricing."
        ),
    },
    {
        "id": "USTR-2026-0308-F",
        "title": "Section 301 Tariff Modifications on Semiconductor Equipment and Critical Minerals",
        "domain": "ustr",
        "source_url": "https://ustr.gov/issue-areas/enforcement/section-301-investigations/tariff-actions-2026",
        "published_date": "2026-03-08",
        "change_type": "amendment",
        "raw_text": (
            "The Office of the United States Trade Representative announces modifications to "
            "the Section 301 tariff actions affecting imports of semiconductor manufacturing "
            "equipment and critical minerals from the People's Republic of China. Effective "
            "April 15, 2026, ad valorem tariff rates will increase from 25% to 50% on "
            "lithography equipment (HTS 8486.20), etching machines (HTS 8486.10), and ion "
            "implantation equipment (HTS 8486.40). Additionally, tariffs on refined rare earth "
            "elements (HTS 2846) will increase from 0% to 25%. An exclusion process will be "
            "available for importers demonstrating no viable alternative source. These "
            "modifications are expected to impact semiconductor fabrication cost structures "
            "and supply chains for defense and consumer electronics sectors."
        ),
    },
    # ── Real regulatory document (source: federalregister.gov) ──────────────
    {
        # Release No. 33-11216 — adopted July 26, 2023; effective September 5, 2023.
        # Source: https://www.federalregister.gov/documents/2023/08/04/2023-15927/
        #         cybersecurity-risk-management-strategy-governance-and-incident-disclosure
        "id": "SEC-2023-0726-CYB",
        "title": (
            "Cybersecurity Risk Management, Strategy, Governance, and Incident Disclosure"
            " — Final Rule (Release Nos. 33-11216, 34-97989)"
        ),
        "domain": "sec",
        "source_url": (
            "https://www.federalregister.gov/documents/2023/08/04/2023-15927/"
            "cybersecurity-risk-management-strategy-governance-and-incident-disclosure"
        ),
        "published_date": "2023-08-04",
        "change_type": "final_rule",
        "raw_text": (
            "The Securities and Exchange Commission is adopting rules to enhance and "
            "standardize disclosures regarding cybersecurity risk management, strategy, "
            "governance, and incidents by public companies that are subject to the reporting "
            "requirements of the Securities Exchange Act of 1934. The Commission is adopting "
            "amendments to Form 8-K to require registrants to disclose material cybersecurity "
            "incidents within four business days of determining that a cybersecurity incident "
            "is material. The Commission is also adopting amendments to Regulation S-K to "
            "require registrants to provide periodic disclosures about their cybersecurity risk "
            "management, strategy, and governance in annual reports on Form 10-K. "
            "ITEM 1.05 OF FORM 8-K — MATERIAL CYBERSECURITY INCIDENTS. "
            "A registrant shall disclose any cybersecurity incident that the registrant "
            "determines to be material and shall describe the material aspects of the nature, "
            "scope, and timing of the incident, and the material impact or reasonably likely "
            "material impact on the registrant. Such disclosure shall be made within four "
            "business days after the registrant determines that a cybersecurity incident it "
            "has experienced is material. "
            "§ 229.106 CYBERSECURITY RISK MANAGEMENT, STRATEGY, GOVERNANCE, AND INCIDENTS. "
            "(a) Cybersecurity risk management. Describe the registrant's processes, if any, "
            "for assessing, identifying, and managing material risks from cybersecurity threats "
            "in sufficient detail for a reasonable investor to understand those processes. "
            "(b) Management's role. Describe management's role in assessing and managing the "
            "registrant's material risks from cybersecurity threats. "
            "(c) Board oversight. Describe the board of directors' oversight of risks from "
            "cybersecurity threats. If any board committee or subcommittee is responsible for "
            "oversight of cybersecurity risks, identify any such committee or subcommittee and "
            "describe the processes by which the board or such committee is informed about such "
            "risks. "
            "COMPLIANCE DATES. Large accelerated filers: annual reports for fiscal years ending "
            "on or after December 15, 2023. All other registrants: annual reports for fiscal "
            "years ending on or after December 15, 2024. Form 8-K and 6-K disclosures: "
            "December 18, 2023 for large accelerated filers; June 15, 2024 for all others. "
            "Smaller reporting companies: Form 8-K disclosure obligations begin June 15, 2024. "
            "DEFINITIONS. The term 'cybersecurity incident' means an unauthorized occurrence, "
            "or a series of related unauthorized occurrences, on or conducted through a "
            "registrant's information systems that jeopardizes the confidentiality, integrity, "
            "or availability of a registrant's information systems or any information residing "
            "therein. The term 'cybersecurity threat' means any potential unauthorized "
            "occurrence on or conducted through a registrant's information systems that may "
            "result in adverse effects on the confidentiality, integrity, or availability of "
            "a registrant's information systems or any information residing therein."
        ),
    },
]

MOCK_ANALYSES: dict[str, dict] = {
    "SEC-2026-0312-A": {
        "summary": "The SEC adopts final rules requiring climate-related disclosures in registration statements and annual reports, including GHG emissions (Scopes 1-3), transition plans, and governance oversight.",
        "change_type": "final_rule",
        "severity": "critical",
        "affected_business_lines": [
            "Public Equities",
            "ESG / Sustainability",
            "Corporate Finance",
            "Audit & Assurance",
            "Investor Relations",
            "Investment Banking",
        ],
        "affected_regulations": [
            "Regulation S-K",
            "Regulation S-X",
            "Securities Act of 1933",
            "Securities Exchange Act of 1934",
        ],
        "compliance_deadline": "2026-12-15",
        "action_items": [
            "[Legal] Review all current 10-K/10-Q disclosures for climate language gaps",
            "[Compliance] Establish GHG emissions measurement & reporting infrastructure for Scopes 1-3",
            "[Risk] Assess portfolio exposure to companies with material climate risk disclosures",
            "[Ops] Implement data collection pipelines for Scope 3 upstream/downstream emissions",
            "[Tech] Evaluate third-party ESG data vendors for emissions factor databases",
            "[Investor Relations] Prepare board governance narrative for climate oversight",
        ],
        "risk_summary": "Non-compliance exposes the firm to SEC enforcement actions, comment letters, and reputational damage.",
        "confidence": 0.95,
    },
    "CFPB-2026-0228-B": {
        "summary": "CFPB issues supervisory guidance requiring creditors using AI/ML in credit underwriting to provide specific adverse action notices and demonstrate model validation, bias testing, and quarterly re-validation.",
        "change_type": "guidance",
        "severity": "high",
        "affected_business_lines": [
            "Consumer Lending",
            "Credit Cards",
            "Auto Finance",
            "Fintech Partnerships",
            "Mortgage Banking",
            "Collections",
        ],
        "affected_regulations": [
            "Equal Credit Opportunity Act (ECOA)",
            "Fair Credit Reporting Act (FCRA)",
            "Regulation B",
            "Regulation V",
        ],
        "compliance_deadline": None,
        "action_items": [
            "[Compliance] Audit all AI/ML credit models for adverse action notice specificity",
            "[Tech] Implement model explainability tooling (SHAP/LIME) for all production credit models",
            "[Risk] Conduct bias testing across all protected classes with quarterly cadence",
            "[Legal] Update model governance policy to include CFPB explainability expectations",
            "[Ops] Establish model re-validation pipeline with automated drift detection",
        ],
        "risk_summary": "Institutions over $10B face immediate supervisory examination. Failure to demonstrate model transparency may trigger enforcement actions.",
        "confidence": 0.92,
    },
    "FED-2026-0305-C": {
        "summary": "The Federal Reserve proposes enhanced prudential standards for banks custodying crypto-assets, requiring asset segregation, modified Basel III capital charges, quarterly stress testing, and board-level attestations.",
        "change_type": "proposed_rule",
        "severity": "high",
        "affected_business_lines": [
            "Digital Assets / Crypto",
            "Commercial Banking",
            "Risk Management",
            "Treasury & ALM",
            "Capital Markets",
            "Payments",
        ],
        "affected_regulations": [
            "Basel III Framework",
            "Bank Holding Company Act",
            "Federal Reserve Act Section 9",
            "Regulation Y",
        ],
        "compliance_deadline": None,
        "action_items": [
            "[Legal] Submit comment letter within 90-day window addressing capital charge methodology",
            "[Risk] Model capital impact under proposed volatility-based charges",
            "[Tech] Architect custodial infrastructure ensuring full segregation of client vs proprietary crypto-assets",
            "[Compliance] Develop board-level attestation process for crypto risk governance",
            "[Ops] Design quarterly stress testing framework for cyber and operational resilience",
        ],
        "risk_summary": "Mid-size institutions face estimated $2-5M compliance costs. Banks without segregated custody infrastructure risk forced exit from crypto-asset services.",
        "confidence": 0.88,
    },
    "FDA-2026-0301-D": {
        "summary": "FDA issues draft guidance for Predetermined Change Control Plans (PCCPs) allowing AI/ML medical device manufacturers to pre-specify modification protocols.",
        "change_type": "guidance",
        "severity": "medium",
        "affected_business_lines": [
            "Medical Devices",
            "Digital Health / SaMD",
            "Regulatory Affairs",
            "Biotech",
            "Clinical Trials",
        ],
        "affected_regulations": [
            "21 CFR Part 820",
            "Federal Food, Drug, and Cosmetic Act Section 510(k)",
            "De Novo Classification",
            "PMA Regulations",
        ],
        "compliance_deadline": None,
        "action_items": [
            "[Regulatory Affairs] Evaluate existing SaMD portfolio for PCCP eligibility",
            "[Tech] Document ML model modification protocols with validation testing specs",
            "[Legal] Submit comments within 60-day window on PCCP scope and Class III applicability",
            "[Compliance] Develop internal PCCP template aligned with FDA's three-part framework",
            "[Risk] Assess impact assessment methodology requirements for continuous learning algorithms",
        ],
        "risk_summary": "Lack of adoption means continued per-change 510(k) submissions, increasing time-to-market by 6-12 months per model update.",
        "confidence": 0.90,
    },
    "EPA-2026-0215-E": {
        "summary": "EPA finalizes revised PM2.5 annual standard from 9.0 to 8.0 µg/m³. States must submit revised implementation plans within 24 months.",
        "change_type": "final_rule",
        "severity": "high",
        "affected_business_lines": [
            "Manufacturing",
            "Energy & Utilities",
            "Transportation",
            "Real Estate & Construction",
            "Insurance (Environmental)",
            "Agriculture",
        ],
        "affected_regulations": [
            "Clean Air Act Section 109",
            "NAAQS",
            "Title V Permitting",
            "State Implementation Plans",
            "New Source Review",
        ],
        "compliance_deadline": "2028-02-15",
        "action_items": [
            "[Ops] Inventory all facilities in potential non-attainment areas under new 8.0 µg/m³ standard",
            "[Legal] Assess exposure to stricter Title V permit conditions across the portfolio",
            "[Risk] Model financial impact of increased emissions offset requirements",
            "[Compliance] Engage with state environmental agencies on SIP revision timelines",
            "[Tech] Evaluate PM2.5 monitoring and reduction technologies for key facilities",
        ],
        "risk_summary": "Non-attainment redesignation could halt new industrial permitting and require expensive retrofits.",
        "confidence": 0.91,
    },
    "FHFA-2026-0310-G": {
        "summary": "FHFA raises 2026 conforming loan limits to $806,500 and updates Agency MBS collateral haircut schedules for securities lending, effective May 1, 2026.",
        "change_type": "notice",
        "severity": "medium",
        "affected_business_lines": [
            "Agency Lending",
            "Agency MBS / TBA",
            "GSE Collateral Management",
            "Conforming Loan Origination",
            "Mortgage Banking",
            "Prepayment Modelling",
        ],
        "affected_regulations": [
            "FHFA Conforming Loan Limits (12 USC 1717)",
            "Fannie Mae Selling Guide",
            "Freddie Mac Single-Family Seller/Servicer Guide",
            "Securities Lending Collateral Schedules",
        ],
        "compliance_deadline": "2026-05-01",
        "action_items": [
            "[Agency Lending] Update collateral eligibility systems for new $806,500 / $1,209,750 high-cost limits",
            "[Agency MBS] Re-price TBA forward commitments near the new loan limit threshold",
            "[GSE Collateral] Implement revised haircut matrix reflecting updated duration risk and prepayment volatility",
            "[Risk] Recalibrate prepayment models for new conforming universe composition",
            "[Ops] Update loan delivery systems and investor reporting for revised limits",
        ],
        "risk_summary": "Failure to update collateral systems by May 1 creates settlement risk and potential over-collateralisation in sec lending programs.",
        "confidence": 0.93,
    },
    "OCC-2026-0308-H": {
        "summary": "Interagency guidance tightens leveraged lending standards: max debt/EBITDA reduced to 5.5x, leveraged definition expanded to 4.0x EBITDA, mandatory maintenance covenants in 50% of new facilities.",
        "change_type": "guidance",
        "severity": "high",
        "affected_business_lines": [
            "Secured Lending",
            "Prime Lending",
            "Leveraged Finance",
            "Credit Portfolio Management",
            "Capital Planning",
            "Commercial Real Estate Lending",
        ],
        "affected_regulations": [
            "OCC Bulletin 2013-9 (Leveraged Lending)",
            "Federal Reserve SR 13-3",
            "FDIC FIL-13-2013",
            "Dodd-Frank Act Section 165",
        ],
        "compliance_deadline": "2026-09-08",
        "action_items": [
            "[Secured Lending] Audit existing leveraged loan portfolio against 5.5x EBITDA threshold; flag exceptions",
            "[Credit] Update underwriting policy and credit approval templates with new debt/EBITDA limits",
            "[Legal] Review covenant structures across pipeline deals for maintenance covenant compliance",
            "[Risk] Model capital impact of enhanced supervisory review trigger at 3x Tier 1 capital",
            "[Portfolio] Identify loans where expanded leveraged definition changes internal classification and pricing",
            "[Compliance] Submit updated leveraged lending policy to OCC examiner within 180-day window",
        ],
        "risk_summary": "Portfolio exceeding 3x Tier 1 capital in leveraged loans triggers enhanced supervisory review. Non-compliant underwriting standards risk MRA/MRIA findings.",
        "confidence": 0.91,
    },
    "FINRA-2026-0305-I": {
        "summary": "FINRA Rule 4210 amendments mandate daily variation margin on TBA positions >$10M and initial margin on positions >$50M, effective August 1, 2026. Industry-wide mobilisation estimated at $12-18B.",
        "change_type": "final_rule",
        "severity": "high",
        "affected_business_lines": [
            "Agency Lending",
            "Agency MBS / TBA",
            "Margin Lending",
            "Repo / Reverse Repo",
            "Prime Brokerage",
            "Customer Margin Accounts",
            "Broker-Dealer Operations",
        ],
        "affected_regulations": [
            "FINRA Rule 4210",
            "FINRA Rule 4220",
            "SEC Regulation T",
            "Exchange Act Section 7",
        ],
        "compliance_deadline": "2026-08-01",
        "action_items": [
            "[Prime Brokerage] Implement daily VM calculation engine for TBA net positions exceeding $10M notional",
            "[Risk] Build IM calculation (schedule-based and model-based) for positions above $50M",
            "[Ops] Update customer agreement templates to reflect new TBA margin obligations",
            "[Tech] Integrate Rule 4210 TBA margin into existing margin management system",
            "[Legal] Confirm clearing exemption documentation for exchange-cleared TBA transactions",
            "[Finance] Model liquidity impact of $12-18B industry-wide margin mobilisation on funding costs",
        ],
        "risk_summary": "Non-compliance after August 1 exposes broker-dealer to FINRA enforcement. Margin mobilisation requirement could tighten repo market liquidity.",
        "confidence": 0.94,
    },
    "CFTC-2026-0301-J": {
        "summary": "UMR Phase 6 final rules adopt SIMM v2.7, increasing IM requirements 8-15% for IR and credit derivatives. Quarterly ANA recertification required. Effective September 1, 2026.",
        "change_type": "final_rule",
        "severity": "high",
        "affected_business_lines": [
            "Derivatives / Swaps",
            "Initial Margin (IM/SIMM)",
            "Counterparty Credit Risk",
            "CVA / MVA Hedging",
            "FX Prime Brokerage",
            "XVA Desk",
        ],
        "affected_regulations": [
            "CFTC Regulation 23.150-161 (Margin)",
            "Dodd-Frank Act Section 4s(e)",
            "ISDA SIMM v2.7",
            "Basel III Uncleared Margin Rules",
        ],
        "compliance_deadline": "2026-09-01",
        "action_items": [
            "[XVA Desk] Recalibrate MVA pricing models to reflect SIMM v2.7 increased IM requirements",
            "[Counterparty Risk] Recompute initial margin exposure under new supervisory factors for all counterparties",
            "[Ops] Update SIMM calculation engine to v2.7 and validate against ISDA CRIF v2.7 format",
            "[Legal] Implement quarterly ANA recertification process with documented threshold monitoring",
            "[Finance] Assess custodial cost increases from higher segregated IM balances",
            "[Risk] Stress test cross-currency swap delta sensitivity changes for largest IR books",
        ],
        "risk_summary": "8-15% IM increase directly raises MVA and funding costs. Entities near $50B ANA threshold need daily monitoring to avoid crossing into Phase 6 requirements.",
        "confidence": 0.90,
    },
    "FDIC-2026-0225-K": {
        "summary": "FDIC imposes special surcharge of 13.4bps on uninsured deposits >$5B for banks >$50B assets, plus revised base assessment rates raising cost by up to 8bps. Effective Q2 2026.",
        "change_type": "final_rule",
        "severity": "high",
        "affected_business_lines": [
            "Commercial Banking",
            "Deposit Funding",
            "Capital Adequacy",
            "Secured Lending",
            "Stress Testing",
            "Brokered Deposits",
        ],
        "affected_regulations": [
            "Federal Deposit Insurance Act Section 7 (12 USC 1817)",
            "12 CFR Part 327",
            "FDIC Assessment Rate Schedule",
        ],
        "compliance_deadline": "2026-04-01",
        "action_items": [
            "[Finance] Model funding cost increase from 13.4bps surcharge on uninsured deposits",
            "[Treasury] Reassess economics of brokered deposit programs given 50% higher weighting in assessments",
            "[Capital] Update net interest margin projections to reflect revised assessment rate schedule",
            "[Ops] Implement quarterly surcharge calculation and payment process by Q2 2026",
            "[Risk] Stress test deposit beta assumptions with elevated assessment costs in NIM models",
        ],
        "risk_summary": "Aggregate industry cost of $15.8B will pressure NIM and deposit funding strategies. Brokered deposit reliance now carries significantly higher cost.",
        "confidence": 0.92,
    },
    "BASEL-2026-0315-L": {
        "summary": "Basel IV output floor confirmed at 72.5% of SA RWA by 2028, phasing from 50% now. Revised SA-CR lowers repo risk weights to 65% with daily margining. IRBA parallel runs required by Q3 2026.",
        "change_type": "final_rule",
        "severity": "critical",
        "affected_business_lines": [
            "Capital Optimization",
            "RWA Modelling",
            "SA-CCR",
            "Leverage Ratio / SLR",
            "NSFR / LCR",
            "Output Floor",
            "Internal Models (FRTB / IRBA)",
            "XVA Desk",
        ],
        "affected_regulations": [
            "Basel III / Basel IV (BCBS d424)",
            "CRR3 (EU)",
            "Basel IV Output Floor",
            "SA-CR",
            "SA-CCR",
            "FRTB",
        ],
        "compliance_deadline": "2026-09-30",
        "action_items": [
            "[Capital Optimization] Model output floor binding scenarios at 55%, 65%, 72.5% RWA floor trajectories",
            "[RWA Modelling] Begin parallel IRBA vs SA-CR output floor runs for secured lending and repo books",
            "[SA-CCR] Update counterparty credit risk models with revised supervisory factors for IR options",
            "[XVA Desk] Recalibrate KVA pricing to incorporate output floor capital cost trajectory",
            "[Risk] Assess repo book eligibility for 65% risk weight treatment (daily margining documentation)",
            "[Compliance] Submit output floor parallel run framework to lead supervisor by Q3 2026",
        ],
        "risk_summary": "Output floor will bind for institutions with advanced IRBA models, potentially increasing RWA 15-30% vs current levels. Capital optimization strategies must be re-run.",
        "confidence": 0.95,
    },
    "FED-2026-0312-M": {
        "summary": "CCAR 2026 severely adverse scenario: 500bps BBB spread widening, 10Y UST at 0.75%, S&P -55%, unemployment 10%. Exploratory shock adds 300bps repo rate spike for 30 days. Plans due April 5.",
        "change_type": "notice",
        "severity": "critical",
        "affected_business_lines": [
            "Stress Testing",
            "Capital Planning",
            "Repo / Reverse Repo",
            "Prime Lending",
            "Secured Lending",
            "Leveraged Finance",
            "Capital Optimization",
        ],
        "affected_regulations": [
            "Dodd-Frank Act Section 165(i)",
            "12 CFR Part 252 (Regulation YY)",
            "Federal Reserve SR 15-18",
            "CCAR Instructions 2026",
        ],
        "compliance_deadline": "2026-04-05",
        "action_items": [
            "[Stress Testing] Run P&L and capital impact models against severely adverse scenario across all desks",
            "[Repo / Secured] Stress test securities financing book under 300bps repo rate spike for 30-day window",
            "[Prime Lending] Model customer margin call cascades under S&P -55% scenario",
            "[Capital Planning] Submit capital plan to Federal Reserve by April 5 deadline",
            "[Risk] Quantify leveraged loan mark-to-market losses under 500bps BBB spread widening",
            "[Liquidity] Model funding cliff risk under simultaneous BBB spread and repo rate stress",
        ],
        "risk_summary": "Repo spike exploratory scenario directly stresses securities financing P&L. 30-day 300bps repo dislocation could materially impair prime and secured lending economics.",
        "confidence": 0.97,
    },
    "FED-2026-0303-N": {
        "summary": "SR 11-7 updated to explicitly cover AI/ML and optimization models. Optimizer models for capital allocation require Tier 1 validation annually. Challenger models mandatory. Examiners assess AI/ML governance from Q3 2026.",
        "change_type": "guidance",
        "severity": "high",
        "affected_business_lines": [
            "Model Risk Management",
            "Capital Optimization",
            "RWA Modelling",
            "Stress Testing",
            "Credit Portfolio Management",
            "XVA Desk",
        ],
        "affected_regulations": [
            "Federal Reserve SR 11-7",
            "OCC Bulletin 2011-12",
            "Federal Reserve SR 15-18",
            "Dodd-Frank Section 165",
        ],
        "compliance_deadline": None,
        "action_items": [
            "[Model Risk] Update model inventory to include all optimization, allocation, and ML production models",
            "[Validation] Schedule Tier 1 re-validation for all capital allocation and portfolio optimization models",
            "[Data Science] Implement concept drift monitoring with formal retraining triggers for all online learning models",
            "[Governance] Develop and maintain challenger models for each production optimization algorithm",
            "[Documentation] Update model documentation to SR 11-7 standards for optimizer and RL models",
            "[Compliance] Prepare AI/ML model governance materials for Q3 2026 examiner review",
        ],
        "risk_summary": "Optimization models used for capital allocation are now explicitly in scope. Lack of challengers or Tier 1 validation creates MRA risk in Q3 2026 examinations.",
        "confidence": 0.93,
    },
    "SEC-2026-0295-O": {
        "summary": "Rule 15c3-3 amendments raise collateral coverage to 102%, restrict equity collateral to 30%, eliminate non-HQLA fixed income collateral, and cap rehypothecation at 140% of net debit balance. 270-day compliance window.",
        "change_type": "final_rule",
        "severity": "high",
        "affected_business_lines": [
            "Securities Lending",
            "Prime Brokerage",
            "Customer Margin Accounts",
            "Repo / Reverse Repo",
            "Broker-Dealer Operations",
        ],
        "affected_regulations": [
            "SEC Rule 15c3-3",
            "Exchange Act Section 15(c)(3)",
            "SEC Rule 15c3-1 (Net Capital)",
            "FINRA Rule 4160",
        ],
        "compliance_deadline": "2026-11-20",
        "action_items": [
            "[Securities Lending] Update collateral management system to enforce 102% coverage with same-day margin call triggers",
            "[Prime Brokerage] Implement 30% equity collateral cap per counterparty with real-time concentration monitoring",
            "[Ops] Remove non-HQLA fixed income from eligible collateral schedules for customer securities loans",
            "[Risk] Recalibrate rehypothecation limits to 140% of net debit balance across all prime accounts",
            "[Legal] Update customer agreement templates to reflect collateral substitution consent requirements",
            "[Finance] Model funding impact of higher collateral quality requirements and reduced rehypothecation",
        ],
        "risk_summary": "Rehypothecation cap and higher collateral quality requirements directly reduce prime brokerage revenue. Non-HQLA collateral elimination increases funding costs.",
        "confidence": 0.91,
    },
    "CFTC-2026-0310-P": {
        "summary": "SA-CCR guidance clarifies 0% supervisory factor for repo <10 days with daily margin; raises non-IG collateral factor to 2.0%. Combined repo/derivative netting set treatment clarified. Methodology submissions due June 30.",
        "change_type": "guidance",
        "severity": "medium",
        "affected_business_lines": [
            "SA-CCR",
            "Counterparty Credit Risk",
            "Repo / Reverse Repo",
            "Derivatives / Swaps",
            "XVA Desk",
            "Capital Optimization",
        ],
        "affected_regulations": [
            "CFTC Regulation 23.151 (SA-CCR)",
            "Basel III SA-CCR Framework",
            "17 CFR Part 23",
            "CFTC Capital Rules",
        ],
        "compliance_deadline": "2026-06-30",
        "action_items": [
            "[SA-CCR] Confirm daily margining documentation for repos <10 days to qualify for 0% supervisory factor",
            "[Counterparty Risk] Update non-IG repo collateral supervisory factor from 1.5% to 2.0% in EAD models",
            "[XVA Desk] Recalibrate CVA for combined repo/OTC netting sets at prime brokerage business",
            "[Capital] Model EAD reduction from 0% factor qualification across eligible short-dated repo book",
            "[Compliance] Submit updated SA-CCR calculation methodology to lead supervisor by June 30",
        ],
        "risk_summary": "0% supervisory factor qualification could significantly reduce EAD and capital for short-dated repo. Non-IG collateral reclassification increases EAD by ~33% for affected positions.",
        "confidence": 0.88,
    },
    "USTR-2026-0308-F": {
        "summary": "USTR doubles Section 301 tariffs on Chinese semiconductor equipment (25% → 50%) and imposes new 25% tariffs on refined rare earth elements, effective April 15, 2026.",
        "change_type": "amendment",
        "severity": "critical",
        "affected_business_lines": [
            "Semiconductor Manufacturing",
            "Supply Chain / Procurement",
            "Defense Contracting",
            "Consumer Electronics",
            "Critical Minerals",
            "International Trade Finance",
        ],
        "affected_regulations": [
            "Trade Act of 1974 Section 301",
            "Harmonized Tariff Schedule (HTS)",
            "Export Administration Regulations (EAR)",
        ],
        "compliance_deadline": "2026-04-15",
        "action_items": [
            "[Procurement] Audit supplier exposure to affected HTS codes (8486.20, 8486.10, 8486.40, 2846)",
            "[Legal] File tariff exclusion requests for equipment with no viable non-China source",
            "[Risk] Model cost impact of 50% tariff on semiconductor fab capex budgets",
            "[Ops] Identify and qualify alternative suppliers in allied nations (Japan, Netherlands, South Korea)",
            "[Finance] Reassess inventory hedging strategies for rare earth element procurement",
            "[Compliance] Monitor Federal Register for exclusion process details and deadlines",
        ],
        "risk_summary": "Immediate 30-day action window before April 15 effective date. Semiconductor fabrication costs could increase 15-25%.",
        "confidence": 0.94,
    },
    # Real document: SEC Release 33-11216 (July 2023)
    "SEC-2023-0726-CYB": {
        "summary": (
            "SEC final rule mandates 4-business-day Form 8-K disclosure of material "
            "cybersecurity incidents and annual 10-K disclosures of cybersecurity risk "
            "management processes, board oversight, and management's role. Large accelerated "
            "filers effective December 15, 2023; all others June 15, 2024."
        ),
        "change_type": "final_rule",
        "severity": "high",
        "affected_business_lines": [
            "Information Security / CISO",
            "Legal / General Counsel",
            "Investor Relations",
            "Risk Management",
            "Board / Governance",
            "Public Disclosure / SEC Reporting",
        ],
        "affected_regulations": [
            "Securities Exchange Act of 1934",
            "Regulation S-K § 229.106",
            "Form 8-K Item 1.05",
            "Form 10-K Item 1C",
            "Form 6-K / Form 20-F (foreign private issuers)",
            "SEC Release No. 33-11216 / 34-97989",
        ],
        "compliance_deadline": "2023-12-15",
        "action_items": [
            "[CISO] Establish internal escalation and materiality-determination protocol with 4-business-day Form 8-K trigger",
            "[Legal] Draft template 8-K Item 1.05 disclosure language and review committee charter",
            "[IR] Coordinate with Legal on timing and content of cybersecurity incident public disclosures",
            "[Risk] Develop board-level cybersecurity risk dashboard and briefing cadence (per Item 106(c))",
            "[SEC Reporting] Add Item 1C cybersecurity risk management section to 10-K template",
            "[Governance] Update board committee charters to formalize cybersecurity oversight responsibility",
            "[IT] Ensure incident detection and classification systems can support 4-day disclosure window",
        ],
        "risk_summary": (
            "Non-compliance exposes registrants to SEC enforcement, comment letters, and "
            "private litigation. The 4-business-day clock starts at materiality determination, "
            "not incident discovery — internal triage processes are the critical path."
        ),
        "confidence": 0.97,
    },
}
