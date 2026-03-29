"""Skill: Regulatory Regime Detection.

Identifies which macro-prudential regulatory regimes are *active* based on
signal language patterns across recent filings.  The output deliberately
informs rather than prescribes — it tells the user which regimes are
consistent with the language observed in regulatory artifacts, leaving action
decisions to the practitioner.

Regime archetypes cover the full prudential / market-infrastructure spectrum:
    - Prudential capital tightening cycles (Basel IV, GSIB surcharges, SCB)
    - Supervisory scrutiny intensification (MRA/MRIA density, horizontal exams)
    - Liquidity stress response (LCR/NSFR tightening, HQLA reclassification)
    - Derivatives and margin reform (SA-CCR, UMR, SIMM recalibration)
    - Climate / ESG integration (transition risk, physical risk, TCFD)
    - Digital asset regulatory capture (stablecoins, SAB 121/122, custody)
    - Resolution / TLAC tightening (bail-in mechanics, living wills)
    - FRTB / market risk model implementation (IMA approvals, ES recalibration)
    - Agency / GSE reform (conforming limits, g-fees, CRT)
    - Consumer protection and fair lending scrutiny (UDAAP, redlining)

Two-pass execution:
    Pass 1  — keyword scoring across all memory records (fast, no LLM cost)
    Pass 2  — LLM synthesis converts scored signals into structured regime state
              with phase assessments (emergence → acceleration → peak → deceleration)
"""

from __future__ import annotations

import re
from typing import Any

from app.naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)
from app.naturalsentinel.utils.parsing import parse_llm_json

# ── Regime taxonomy ─────────────────────────────────────────────────────────

REGIME_ARCHETYPES: list[dict] = [
    {
        "id": "prudential_capital_tightening",
        "label": "Prudential Capital Tightening Cycle",
        "description": (
            "Regulatory bodies are raising minimum capital requirements, "
            "constraining internal model optionality, or imposing new floors on "
            "standardised-approach calculations. Typical indicators: Basel IV "
            "output floor phase-in, GSIB surcharge recalibration, higher SCB, "
            "or reduced IRB optionality."
        ),
        "signal_terms": [
            "output floor",
            "standardised approach floor",
            "irb constraints",
            "gsib surcharge",
            "stress capital buffer",
            "scb",
            "higher capital",
            "capital add-on",
            "pillar 2 add-on",
            "rwa inflation",
            "risk weight floor",
            "model constraints",
            "revised standardised approach",
            "internal ratings-based",
            "irba restrictions",
            "leverage ratio buffer",
            "tier 1 capital",
            "cet1 requirement",
            "capital surcharge",
            "conservation buffer",
            "countercyclical buffer",
        ],
        "domains": ["BASEL", "FED", "OCC", "FDIC"],
    },
    {
        "id": "supervisory_scrutiny_intensification",
        "label": "Supervisory Scrutiny Intensification",
        "description": (
            "Supervisors are signalling elevated oversight expectations through "
            "increased MRA/MRIA issuance, horizontal examination themes, or "
            "explicit expectations guidance. Often a leading indicator of "
            "enforcement actions or consent orders."
        ),
        "signal_terms": [
            "matters requiring attention",
            "mra",
            "matters requiring immediate attention",
            "mria",
            "horizontal review",
            "supervisory expectations",
            "exam findings",
            "supervisory letter",
            "heightened standards",
            "safety and soundness",
            "corporate governance",
            "risk management expectations",
            "model governance",
            "third-party risk management",
            "tprm",
            "board oversight",
            "audit findings",
            "deficiency letter",
            "supervisory guidance",
            "cease and desist",
        ],
        "domains": ["FED", "OCC", "FDIC", "CFPB"],
    },
    {
        "id": "liquidity_stress_response",
        "label": "Liquidity Stress Response Regime",
        "description": (
            "Regulators are responding to realised or anticipated liquidity "
            "stress by tightening HQLA eligibility, LCR / NSFR calibration, "
            "or contingency funding requirements. Typically follows bank "
            "failures or pronounced market dislocation."
        ),
        "signal_terms": [
            "hqla",
            "high-quality liquid assets",
            "lcr",
            "liquidity coverage ratio",
            "nsfr",
            "net stable funding ratio",
            "uninsured deposits",
            "concentrated funding",
            "contingency funding plan",
            "cfp",
            "intraday liquidity",
            "ilaap",
            "liquidity stress",
            "funding concentration",
            "fdic insurance limit",
            "liquidity risk management",
            "alt-m",
            "alternative metric",
            "runoff rate",
            "stable funding",
            "available stable funding",
        ],
        "domains": ["FED", "FDIC", "OCC", "BASEL"],
    },
    {
        "id": "derivatives_margin_reform",
        "label": "Derivatives and Margin Reform Cycle",
        "description": (
            "Central counterparty clearing mandates, uncleared margin rules, "
            "or SA-CCR recalibration are actively reshaping the derivatives "
            "exposure and collateral landscape. Phases follow BIS/IOSCO UMR "
            "timelines or CFTC clearing mandate expansions."
        ),
        "signal_terms": [
            "initial margin",
            "im requirements",
            "sa-ccr",
            "simm",
            "isda simm",
            "uncleared margin",
            "umr",
            "phase-in",
            "threshold amount",
            "cleared derivatives",
            "bilateral margin",
            "variation margin",
            "ccp margin",
            "cem replacement",
            "current exposure method",
            "alpha factor",
            "supervisory factor",
            "netting set",
            "eligible collateral",
            "segregation requirements",
        ],
        "domains": ["CFTC", "FED", "BASEL"],
    },
    {
        "id": "climate_esg_integration",
        "label": "Climate and ESG Integration Regime",
        "description": (
            "Supervisors and standard-setters are embedding climate and ESG "
            "factors into prudential frameworks through stress testing scenarios, "
            "risk weight adjustments, or mandatory disclosure regimes."
        ),
        "signal_terms": [
            "climate risk",
            "transition risk",
            "physical risk",
            "climate scenario",
            "scope 3",
            "green asset",
            "sustainable finance",
            "esg",
            "climate stress test",
            "taxonomy",
            "sfdr",
            "tcfd",
            "ifrs s2",
            "climate-related financial risk",
            "stranded assets",
            "net zero",
            "carbon intensity",
            "climate scenario analysis",
            "paris agreement",
            "greenwashing",
            "sustainability disclosure",
            "environmental risk",
        ],
        "domains": ["FED", "SEC", "OCC", "FDIC", "BASEL"],
    },
    {
        "id": "digital_asset_regulatory_capture",
        "label": "Digital Asset Regulatory Capture Phase",
        "description": (
            "Regulators are establishing or clarifying frameworks for digital "
            "assets, crypto-asset custody, stablecoin issuance, or tokenised "
            "securities. Characterised by rapid, sometimes conflicting, guidance."
        ),
        "signal_terms": [
            "digital asset",
            "crypto",
            "stablecoin",
            "cryptocurrency",
            "virtual currency",
            "sab 121",
            "sab 122",
            "custody of digital assets",
            "tokenized",
            "tokenised",
            "distributed ledger",
            "blockchain",
            "defi",
            "decentralised finance",
            "crypto-asset",
            "cbdc",
            "central bank digital currency",
            "digital wallet",
            "spot bitcoin etf",
            "crypto exchange",
        ],
        "domains": ["SEC", "CFTC", "OCC", "FED"],
    },
    {
        "id": "resolution_tlac_tightening",
        "label": "Resolution Planning and TLAC Tightening",
        "description": (
            "Regulators are raising gone-concern loss-absorbing capacity "
            "requirements, updating resolution planning expectations, or "
            "refining bail-in mechanics. Often accompanies systemic risk "
            "concerns or post-crisis reviews."
        ),
        "signal_terms": [
            "tlac",
            "total loss-absorbing capacity",
            "mrel",
            "internal tlac",
            "resolution plan",
            "living will",
            "gone-concern",
            "bail-in",
            "recapitalisation",
            "point of non-viability",
            "ponv",
            "resolution strategy",
            "preferred resolution",
            "spoe",
            "mpoe",
            "issuance requirement",
            "eligible instruments",
            "resolution liquidity",
            "resolution funding",
        ],
        "domains": ["FED", "FDIC", "FSOC", "BASEL"],
    },
    {
        "id": "frtb_model_implementation",
        "label": "FRTB and Market Risk Model Implementation",
        "description": (
            "Internal model approach (IMA) approvals, expected shortfall "
            "recalibration, trading / banking book boundary reviews, or "
            "non-modellable risk factor treatments are actively being "
            "implemented or revised."
        ),
        "signal_terms": [
            "frtb",
            "fundamental review of the trading book",
            "internal model approach",
            "ima",
            "expected shortfall",
            "p&l attribution",
            "pla test",
            "trading book boundary",
            "risk factor eligibility",
            "nmrf",
            "non-modellable risk factor",
            "backtesting exceptions",
            "sensitivities-based method",
            "default risk charge",
            "drc",
            "stressed expected shortfall",
            "desk-level approval",
        ],
        "domains": ["BASEL", "FED", "OCC"],
    },
    {
        "id": "agency_gse_reform",
        "label": "Agency and GSE Reform Cycle",
        "description": (
            "FHFA is adjusting guarantee fee structures, credit risk transfer "
            "programmes, conforming loan limits, or conservatorship conditions "
            "for Fannie Mae / Freddie Mac. Signals changing economics for "
            "agency mortgage origination and securitisation."
        ),
        "signal_terms": [
            "conforming loan limit",
            "cll",
            "g-fee",
            "guarantee fee",
            "credit risk transfer",
            "crt",
            "gse",
            "government-sponsored enterprise",
            "fannie mae",
            "freddie mac",
            "fhfa",
            "conservatorship",
            "enterprise capital",
            "tba market",
            "agency mbs",
            "prepayment",
            "housing finance reform",
            "single-family pricing",
        ],
        "domains": ["FHFA"],
    },
    {
        "id": "consumer_fair_lending_scrutiny",
        "label": "Consumer Protection and Fair Lending Scrutiny",
        "description": (
            "Enforcement and supervisory focus is intensifying on consumer "
            "protection violations, fair lending, UDAAP, or discriminatory "
            "credit practices. Associated with CFPB examination cycles or "
            "DOJ referrals."
        ),
        "signal_terms": [
            "udap",
            "udaap",
            "unfair deceptive",
            "fair lending",
            "disparate impact",
            "redlining",
            "fair housing",
            "ecoa",
            "hmda",
            "cra",
            "community reinvestment",
            "fair credit reporting",
            "fcra",
            "consumer complaint",
            "abusive act",
            "prohibited basis",
            "supervisory examination",
            "enforcement action",
        ],
        "domains": ["CFPB", "OCC", "FED", "FDIC"],
    },
    # ── Technology / Telecom Regime Archetypes ────────────────────────────────
    {
        "id": "platform_antitrust_enforcement",
        "label": "Platform Antitrust Enforcement Cycle",
        "description": (
            "Antitrust authorities are intensifying scrutiny of large digital "
            "platforms via merger challenges, conduct investigations, or new "
            "obligations under the EU Digital Markets Act (DMA) or domestic "
            "equivalents. Signals rising breakup risk, interoperability mandates, "
            "or gatekeeper designation for major tech operators."
        ),
        "signal_terms": [
            "digital markets act",
            "dma",
            "gatekeeper",
            "self-preferencing",
            "interoperability",
            "data portability",
            "platform conduct",
            "dominant position",
            "merger challenge",
            "hsr",
            "second request",
            "ftc complaint",
            "doj antitrust",
            "structural remedy",
            "divestiture",
            "vertical integration",
            "app store",
            "default agreements",
            "platform neutrality",
            "algorithmic fairness",
        ],
        "domains": ["FTC", "DOJ"],
    },
    {
        "id": "data_privacy_regulatory_expansion",
        "label": "Data Privacy Regulatory Expansion",
        "description": (
            "New or amended data privacy regimes are extending consent, "
            "data subject rights, cross-border transfer restrictions, or "
            "enforcement authority. Characterised by simultaneous state-level "
            "law activations (US) or adequacy decision changes (EU-US). "
            "Signals elevated compliance build-out obligations for data "
            "processors and controllers."
        ),
        "signal_terms": [
            "gdpr",
            "ccpa",
            "cpra",
            "data subject rights",
            "right to erasure",
            "consent requirement",
            "data processing agreement",
            "dpa",
            "standard contractual clauses",
            "scc",
            "adequacy decision",
            "cross-border transfer",
            "data localisation",
            "data residency",
            "personal data",
            "sensitive data",
            "data broker",
            "opt-out",
            "privacy notice",
            "legitimate interest",
            "biometric data",
        ],
        "domains": ["FTC", "CISA"],
    },
    {
        "id": "ai_governance_regulatory_cycle",
        "label": "AI Governance and Accountability Regime",
        "description": (
            "Regulators are establishing or tightening requirements for AI "
            "systems — covering risk classification, conformity assessments, "
            "transparency obligations, and bias audits. The EU AI Act represents "
            "the primary legislative vector; FTC guidance and state-level "
            "algorithmic accountability laws are concurrent signals. "
            "High-risk AI system operators face the most acute obligations."
        ),
        "signal_terms": [
            "eu ai act",
            "high-risk ai",
            "ai system",
            "conformity assessment",
            "ai risk tier",
            "foundation model",
            "general purpose ai",
            "algorithmic accountability",
            "bias audit",
            "ai transparency",
            "explainability",
            "ai governance",
            "ai oversight",
            "automated decision",
            "profiling",
            "ftc ai",
            "ai liability",
            "ai regulatory sandbox",
            "responsible ai",
            "ai impact assessment",
        ],
        "domains": ["FTC", "SEC"],
    },
    {
        "id": "cybersecurity_mandate_tightening",
        "label": "Cybersecurity Mandate Tightening Cycle",
        "description": (
            "CISA, FCC, and SEC are expanding mandatory cybersecurity obligations "
            "through Known Exploited Vulnerability patching directives, incident "
            "disclosure timelines (SEC Form 8-K), and FCC telecom network security "
            "rules. Executive Order 14028 implementation is the key federal driver; "
            "critical infrastructure sectors face simultaneous sector-specific mandates."
        ),
        "signal_terms": [
            "cisa kev",
            "known exploited vulnerability",
            "binding operational directive",
            "bod",
            "sec 8-k cybersecurity",
            "incident disclosure",
            "material breach",
            "cybersecurity incident",
            "zero day",
            "patch deadline",
            "eo 14028",
            "supply chain security",
            "sbom",
            "software bill of materials",
            "critical infrastructure",
            "network security",
            "ransomware",
            "vulnerability disclosure",
            "fcc cyber",
            "telecom security",
        ],
        "domains": ["CISA", "FCC", "SEC"],
    },
    {
        "id": "spectrum_policy_reform",
        "label": "Spectrum Policy and Licensing Reform Cycle",
        "description": (
            "The FCC is conducting spectrum auctions, reallocating mid-band or "
            "high-band frequencies, imposing new build-out obligations, or "
            "revising universal service fund (USF) contribution methodology. "
            "NTIA broadband funding programmes (BEAD) represent a concurrent "
            "signal. Signals changing interference, deployment, and coverage "
            "obligations for mobile network operators and rural providers."
        ),
        "signal_terms": [
            "spectrum auction",
            "fcc auction",
            "c-band",
            "cbrs",
            "mid-band",
            "mmwave",
            "build-out obligation",
            "coverage requirement",
            "universal service fund",
            "usf",
            "e-rate",
            "lifeline",
            "ntia",
            "bead",
            "broadband equity",
            "rural broadband",
            "interference protection",
            "dynamic spectrum sharing",
            "spectrum licence",
            "frequency allocation",
            "tv white space",
        ],
        "domains": ["FCC", "NTIA"],
    },
    {
        "id": "content_moderation_liability_shift",
        "label": "Content Moderation and Platform Liability Shift",
        "description": (
            "Legislative or judicial changes are narrowing or redefining Section "
            "230 liability protections, activating DSA very-large online platform "
            "(VLOP) obligations, or requiring algorithmic amplification disclosures. "
            "Notice-and-takedown frameworks and mandatory transparency reporting "
            "are key compliance signals for major social, video, and search platforms."
        ),
        "signal_terms": [
            "section 230",
            "platform liability",
            "dsa",
            "digital services act",
            "vlop",
            "very large online platform",
            "notice and takedown",
            "ntd",
            "content moderation",
            "trusted flagger",
            "algorithmic amplification",
            "transparency report",
            "crisis protocol",
            "systemic risk",
            "recommender system",
            "illegal content",
            "hate speech",
            "csam",
            "counter-terrorism",
            "online safety",
            "age verification",
        ],
        "domains": ["FTC", "SEC"],
    },
    {
        "id": "telecom_infrastructure_security",
        "label": "Telecom Infrastructure Security Mandate",
        "description": (
            "FCC and NTIA are implementing supply chain security rules targeting "
            "equipment from designated foreign adversary vendors (Huawei, ZTE), "
            "imposing rip-and-replace obligations, and tightening roaming and "
            "interconnect security standards. CALEA compliance modernisation and "
            "network function virtualisation security are secondary signals."
        ),
        "signal_terms": [
            "rip and replace",
            "huawei",
            "zte",
            "supply chain security",
            "covered equipment",
            "fcc covered list",
            "calea",
            "lawful intercept",
            "roaming security",
            "ss7 vulnerability",
            "network slicing",
            "open ran",
            "trusted vendor",
            "foreign adversary",
            "banning order",
            "reimbursement programme",
            "network function virtualisation",
            "telecom supply chain",
            "subsea cable",
            "landing station",
        ],
        "domains": ["FCC", "CISA", "NTIA"],
    },
    {
        "id": "data_residency_localisation",
        "label": "Data Residency and Cross-Border Data Regime",
        "description": (
            "Governments are imposing or expanding data localisation requirements, "
            "invalidating existing cross-border transfer mechanisms, or enacting "
            "new data sovereignty frameworks. EU-US data transfer adequacy, "
            "China PIPL/DSL provisions, and India DPDP Act are the principal "
            "vectors. Cloud and payments operators face the highest compliance burden."
        ),
        "signal_terms": [
            "data localisation",
            "data sovereignty",
            "data residency",
            "cross-border data transfer",
            "eu-us data privacy framework",
            "schrems",
            "privacy shield",
            "china pipl",
            "dsl",
            "data security law",
            "india dpdp",
            "digital personal data",
            "government access",
            "cloud act",
            "fisa 702",
            "data border",
            "mirror data",
            "local storage requirement",
            "data export restriction",
            "third country transfer",
        ],
        "domains": ["FTC", "CISA"],
    },
]


# ── System / user prompts ────────────────────────────────────────────────────

_REGIME_SYSTEM = """\
You are a senior macro-prudential analyst specialising in regulatory cycle \
identification and regime classification.

Given a set of recent regulatory filings and their pre-scored regime signals \
(keyword frequency across those filings), your task is to:

1. Identify which regulatory regimes are ACTIVE — materially supported by \
   current filing language.
2. Assess each active regime's current PHASE:
       emergence       — first signals appearing; not yet broad-based
       acceleration    — growing filing volume and signal density
       peak            — maximum breadth; most agencies engaged
       deceleration    — implementation winding down; guidance clarifying
3. Identify TRANSITIONS — regimes newly becoming active or fading from the \
   prior period.
4. Produce a concise, evidence-based macro-prudential narrative.

Important: describe what the language suggests, not what firms should do.
Output JSON only — no markdown fences, no prose outside the JSON.
"""

_REGIME_USER_TEMPLATE = """\
ANALYSIS WINDOW: {window_days} days
TOTAL FILINGS SCANNED: {total_filings}
DOMAINS COVERED: {domains_covered}

REGIME SIGNAL SCORES (keyword frequency across filings):
{signal_scores_block}

REPRESENTATIVE FILING EXCERPTS:
{filing_excerpts}

MEMORY CONTEXT (prior regime assessments):
{memory_block}

For each regime with signal_strength > {threshold}, output an active entry.
Regimes at or below the threshold belong in dormant_regimes.

Output schema:
{{
  "active_regimes": [
    {{
      "regime_id": "<id>",
      "regime_label": "<human label>",
      "signal_strength": <float 0-1>,
      "evidence_count": <int>,
      "signal_terms_found": ["<term>", ...],
      "regulatory_bodies_active": ["<body>", ...],
      "regime_phase": "<emergence|acceleration|peak|deceleration>",
      "summary": "<1-2 sentences describing what the language suggests>"
    }}
  ],
  "dormant_regimes": ["<regime_id>", ...],
  "regime_transitions": [
    {{
      "regime_id": "<id>",
      "transition": "<newly_active|fading>",
      "basis": "<brief explanation>"
    }}
  ],
  "analysis_window_days": {window_days},
  "filings_analyzed": {total_filings},
  "confidence": <float 0-1>,
  "summary": "<2-3 sentence macro-prudential narrative>"
}}
"""


# ── Skill ────────────────────────────────────────────────────────────────────


class RegimeDetectionSkill(Skill):
    """
    Detect active macro-prudential regulatory regimes from filing language.

    Uses a two-pass approach:
        Pass 1  — Fast keyword scoring against the regime taxonomy (zero LLM cost)
        Pass 2  — LLM synthesis converts scored signals into a structured regime
                  state with phase assessments and transition detection

    The output deliberately informs rather than prescribes: it names which
    regimes are consistent with observed regulatory language and characterises
    each regime's current phase, without recommending specific firm actions.
    """

    metadata = SkillMetadata(
        name="regime_detection",
        description=(
            "Identify which macro-prudential regulatory regimes are active based "
            "on signal language patterns across recent filings. Returns a "
            "structured regime taxonomy with phase assessments — informs rather "
            "than prescribes."
        ),
        version="1.0.0",
        permissions=Permission.LLM_READ | Permission.MEMORY_READ,
        latency=LatencyClass.MODERATE,
        parameters=[
            SkillParameter(
                "window_days",
                "int",
                "Look-back window in days for filing analysis.",
                required=False,
                default=90,
            ),
            SkillParameter(
                "domains",
                "list[str]",
                "Filter to specific regulatory domains (None = all).",
                required=False,
                default=None,
            ),
            SkillParameter(
                "signal_threshold",
                "float",
                "Minimum normalised signal strength (0-1) to report a regime as active.",
                required=False,
                default=0.10,
            ),
            SkillParameter(
                "raw_filings",
                "list[dict]",
                "Optional list of raw filing dicts for offline / test use.",
                required=False,
                default=None,
            ),
        ],
        returns=(
            "dict — {active_regimes: list[dict], dormant_regimes: list[str], "
            "regime_transitions: list[dict], filings_analyzed: int, "
            "confidence: float, summary: str}"
        ),
        dependencies=[],
        cacheable=False,
        tags=[
            "regime",
            "macro-prudential",
            "classification",
            "cycle-detection",
            "signal",
        ],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        window_days: int = context.params.get("window_days", 90)
        domains: list[str] | None = context.params.get("domains", None)
        signal_threshold: float = float(context.params.get("signal_threshold", 0.10))
        raw_filings: list[dict] = list(context.params.get("raw_filings") or [])

        # ── 1. Gather filings from memory ────────────────────────────────────
        filings: list[Any] = list(raw_filings)

        if context.memory is not None:
            query_domains = domains or [
                "BASEL",
                "FED",
                "OCC",
                "FDIC",
                "CFTC",
                "SEC",
                "CFPB",
                "FHFA",
                "FTC",
                "DOJ",
                "FCC",
                "CISA",
                "NTIA",
            ]
            for domain in query_domains:
                records = context.memory.get_filing_history(
                    domain=domain.lower(), limit=20
                )
                filings.extend(records)

        if not filings:
            empty: dict = {
                "active_regimes": [],
                "dormant_regimes": [r["id"] for r in REGIME_ARCHETYPES],
                "regime_transitions": [],
                "analysis_window_days": window_days,
                "filings_analyzed": 0,
                "confidence": 0.0,
                "summary": "No filings available in memory for regime detection.",
            }
            return SkillResult(skill_name=self.metadata.name, success=True, data=empty)

        # ── 2. Keyword scoring (no LLM) ──────────────────────────────────────
        scored = self._score_regimes(filings)

        # ── 3. LLM synthesis or keyword-only fallback ────────────────────────
        if context.llm is not None:
            data = self._llm_synthesis(
                context, filings, scored, window_days, signal_threshold
            )
        else:
            data = self._keyword_only_result(
                scored, filings, window_days, signal_threshold
            )

        token_usage = data.pop("_token_usage", 0)
        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data=data,
            token_usage=token_usage,
            metadata={"filings_analyzed": len(filings)},
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _filing_text_and_domain(self, filing: Any) -> tuple[str, str]:
        if isinstance(filing, dict):
            text = " ".join(
                [
                    str(filing.get("title", "")),
                    str(filing.get("raw_text", "")),
                    str(filing.get("summary", "")),
                    str(filing.get("risk_summary", "")),
                ]
            )
            domain = str(filing.get("domain", "")).upper()
        else:
            content = getattr(filing, "content", {}) or {}
            inner_filing = (
                content.get("filing", {}) if isinstance(content, dict) else {}
            )
            inner_impact = (
                content.get("impact", {}) if isinstance(content, dict) else {}
            )
            text = " ".join(
                [
                    str(inner_filing.get("title", "")),
                    str(inner_filing.get("raw_text", "")),
                    str(inner_impact.get("summary", "")),
                    str(inner_impact.get("risk_summary", "")),
                ]
            )
            domain = str(
                inner_filing.get("domain") or getattr(filing, "namespace", "") or ""
            ).upper()
        return text.lower(), domain

    def _score_regimes(self, filings: list[Any]) -> list[dict]:
        filing_pairs = [self._filing_text_and_domain(f) for f in filings]
        total = len(filing_pairs)
        scored: list[dict] = []

        for regime in REGIME_ARCHETYPES:
            filings_with_signal = 0
            terms_found: set[str] = set()
            bodies_active: set[str] = set()

            for text, domain in filing_pairs:
                hit = False
                for term in regime["signal_terms"]:
                    pattern = r"\b" + re.escape(term.lower()) + r"\b"
                    if re.search(pattern, text):
                        terms_found.add(term)
                        hit = True
                if hit:
                    filings_with_signal += 1
                    if domain in regime["domains"]:
                        bodies_active.add(domain)

            scored.append(
                {
                    "regime_id": regime["id"],
                    "regime_label": regime["label"],
                    "signal_strength": round(filings_with_signal / max(total, 1), 3),
                    "evidence_count": filings_with_signal,
                    "signal_terms_found": sorted(terms_found),
                    "regulatory_bodies_active": sorted(bodies_active),
                    "regime_description": regime["description"],
                }
            )

        scored.sort(key=lambda x: x["signal_strength"], reverse=True)
        return scored

    def _build_signal_scores_block(self, scored: list[dict]) -> str:
        lines = []
        for s in scored:
            top_terms = s["signal_terms_found"][:5]
            lines.append(
                f"  {s['regime_id']}: strength={s['signal_strength']:.3f}, "
                f"filings_hit={s['evidence_count']}, sample_terms={top_terms}"
            )
        return "\n".join(lines)

    def _build_excerpts(self, filings: list[Any], max_chars: int = 2000) -> str:
        excerpts: list[str] = []
        budget = max_chars
        for filing in filings[:12]:
            text, domain = self._filing_text_and_domain(filing)
            if isinstance(filing, dict):
                title = filing.get("title", "Unknown")
            else:
                content = getattr(filing, "content", {}) or {}
                inner = content.get("filing", {}) if isinstance(content, dict) else {}
                title = inner.get("title", "Unknown")
            snippet = text[:250].replace("\n", " ")
            entry = f"[{domain}] {title}: {snippet}"
            if budget - len(entry) < 0:
                break
            excerpts.append(entry)
            budget -= len(entry)
        return "\n---\n".join(excerpts)

    def _llm_synthesis(
        self,
        context: SkillContext,
        filings: list[Any],
        scored: list[dict],
        window_days: int,
        signal_threshold: float,
    ) -> dict:
        domains_covered = sorted(
            {self._filing_text_and_domain(f)[1] for f in filings} - {""}
        )

        memory_block = "(none)"
        if context.memory is not None:
            try:
                records = context.memory.recall(
                    "regulatory regime cycle prudential phase", top_k=3
                )
                snippets = []
                for rec in records:
                    content = getattr(rec, "content", {}) or {}
                    if isinstance(content, dict):
                        snippets.append(
                            str(content.get("impact", {}).get("summary", ""))[:200]
                        )
                memory_block = "\n".join(snippets) or "(none)"
            except Exception:
                pass

        user_prompt = _REGIME_USER_TEMPLATE.format(
            window_days=window_days,
            total_filings=len(filings),
            domains_covered=", ".join(domains_covered) or "ALL",
            signal_scores_block=self._build_signal_scores_block(scored),
            filing_excerpts=self._build_excerpts(filings),
            memory_block=memory_block,
            threshold=signal_threshold,
        )

        fallback: dict = {
            "active_regimes": [
                {
                    "regime_id": s["regime_id"],
                    "regime_label": s["regime_label"],
                    "signal_strength": s["signal_strength"],
                    "evidence_count": s["evidence_count"],
                    "signal_terms_found": s["signal_terms_found"],
                    "regulatory_bodies_active": s["regulatory_bodies_active"],
                    "regime_phase": "unknown",
                    "summary": s["regime_description"],
                }
                for s in scored
                if s["signal_strength"] > signal_threshold
            ],
            "dormant_regimes": [
                s["regime_id"]
                for s in scored
                if s["signal_strength"] <= signal_threshold
            ],
            "regime_transitions": [],
            "analysis_window_days": window_days,
            "filings_analyzed": len(filings),
            "confidence": 0.5,
            "summary": "LLM synthesis unavailable; keyword scores shown.",
        }

        raw = context.llm.complete(
            system=_REGIME_SYSTEM,
            user=user_prompt,
            temperature=0.1,
        )
        parsed = parse_llm_json(raw, fallback=fallback)
        parsed.setdefault("analysis_window_days", window_days)
        parsed.setdefault("filings_analyzed", len(filings))
        parsed["_token_usage"] = (len(user_prompt) + len(raw)) // 4
        return parsed

    def _keyword_only_result(
        self,
        scored: list[dict],
        filings: list[Any],
        window_days: int,
        signal_threshold: float,
    ) -> dict:
        active = [s for s in scored if s["signal_strength"] > signal_threshold]
        dormant = [
            s["regime_id"] for s in scored if s["signal_strength"] <= signal_threshold
        ]
        return {
            "active_regimes": [
                {
                    "regime_id": s["regime_id"],
                    "regime_label": s["regime_label"],
                    "signal_strength": s["signal_strength"],
                    "evidence_count": s["evidence_count"],
                    "signal_terms_found": s["signal_terms_found"],
                    "regulatory_bodies_active": s["regulatory_bodies_active"],
                    "regime_phase": "unknown",
                    "summary": s["regime_description"],
                }
                for s in active
            ],
            "dormant_regimes": dormant,
            "regime_transitions": [],
            "analysis_window_days": window_days,
            "filings_analyzed": len(filings),
            "confidence": 0.5,
            "summary": (
                f"{len(active)} regime(s) signalled by keyword scoring "
                "(no LLM synthesis — LLM_READ permission not granted)."
            ),
            "_token_usage": 0,
        }
