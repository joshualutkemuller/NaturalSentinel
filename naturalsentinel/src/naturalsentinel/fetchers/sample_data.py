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
]

MOCK_ANALYSES: dict[str, dict] = {
    "SEC-2026-0312-A": {
        "summary": "The SEC adopts final rules requiring climate-related disclosures in registration statements and annual reports, including GHG emissions (Scopes 1-3), transition plans, and governance oversight.",
        "change_type": "final_rule",
        "severity": "critical",
        "affected_business_lines": ["Public Equities", "ESG / Sustainability", "Corporate Finance", "Audit & Assurance", "Investor Relations", "Investment Banking"],
        "affected_regulations": ["Regulation S-K", "Regulation S-X", "Securities Act of 1933", "Securities Exchange Act of 1934"],
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
        "affected_business_lines": ["Consumer Lending", "Credit Cards", "Auto Finance", "Fintech Partnerships", "Mortgage Banking", "Collections"],
        "affected_regulations": ["Equal Credit Opportunity Act (ECOA)", "Fair Credit Reporting Act (FCRA)", "Regulation B", "Regulation V"],
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
        "affected_business_lines": ["Digital Assets / Crypto", "Commercial Banking", "Risk Management", "Treasury & ALM", "Capital Markets", "Payments"],
        "affected_regulations": ["Basel III Framework", "Bank Holding Company Act", "Federal Reserve Act Section 9", "Regulation Y"],
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
        "affected_business_lines": ["Medical Devices", "Digital Health / SaMD", "Regulatory Affairs", "Biotech", "Clinical Trials"],
        "affected_regulations": ["21 CFR Part 820", "Federal Food, Drug, and Cosmetic Act Section 510(k)", "De Novo Classification", "PMA Regulations"],
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
        "affected_business_lines": ["Manufacturing", "Energy & Utilities", "Transportation", "Real Estate & Construction", "Insurance (Environmental)", "Agriculture"],
        "affected_regulations": ["Clean Air Act Section 109", "NAAQS", "Title V Permitting", "State Implementation Plans", "New Source Review"],
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
    "USTR-2026-0308-F": {
        "summary": "USTR doubles Section 301 tariffs on Chinese semiconductor equipment (25% → 50%) and imposes new 25% tariffs on refined rare earth elements, effective April 15, 2026.",
        "change_type": "amendment",
        "severity": "critical",
        "affected_business_lines": ["Semiconductor Manufacturing", "Supply Chain / Procurement", "Defense Contracting", "Consumer Electronics", "Critical Minerals", "International Trade Finance"],
        "affected_regulations": ["Trade Act of 1974 Section 301", "Harmonized Tariff Schedule (HTS)", "Export Administration Regulations (EAR)"],
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
}
