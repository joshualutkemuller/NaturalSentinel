"""
Built-in skill library for NaturalSentinel.

Each skill is a self-contained capability with declared permissions,
input/output schemas, and dependency graphs.

Core Skills:
    fetch_filings       — Retrieve regulatory filings from sources
    analyze_filing      — LLM-powered impact analysis of a single filing
    recall_memory       — Semantic search across persistent memory
    store_memory        — Persist analysis results to memory
    record_feedback     — Record human corrections as precedent memory
    build_context       — Assemble memory context for LLM prompts
    detect_duplicates   — Check filings against seen-state
    generate_briefing   — Produce executive-level regulatory briefing
    scan_cycle          — Full orchestrated scan (composes other skills)
    track_belief        — Prior/posterior belief tracking per topic (Priority 3)

Intelligence Skills:
    alert_threshold          — Flag analyses breaching severity thresholds
    compliance_deadline      — Extract and prioritise compliance deadlines
    trend_analysis           — Detect regulatory escalation patterns over time
    cross_domain_correlation — Find business-line overlaps across agencies
    export_report            — Render compliance reports (markdown/json/csv)
    regime_detection         — Identify active macro-prudential regulatory regimes

Specialist / Desk Skills:
    capital_impact              — RWA, SLR, leverage ratio, and output floor analysis
    model_risk_assessment       — SR 11-7 re-validation and governance obligations
    securities_financing_analysis — Repo, sec lending, haircut, SFTR impacts
    liquidity_ratio_analysis    — LCR, NSFR, HQLA classification changes
    agency_mortgage_analysis    — FHFA/GSE conforming limits, g-fees, CRT, TBA
    counterparty_risk_analysis  — SA-CCR, SIMM/UMR, CVA capital, EAD impacts
    regulatory_reporting_analysis — New/changed reporting obligations and pipeline impacts
    optimization_constraint     — Translate reg changes into optimizer constraint notation
    leveraged_lending_assessment — Leverage thresholds, covenants, CLO risk retention
    stress_testing_signal       — CCAR/DFAST scenario variables mapped to desk P&L

Platform / Digital Regulatory Skills:
    platform_antitrust_impact   — DMA/DSA gatekeeper obligations, FTC/DOJ enforcement signals
    data_privacy_obligation     — GDPR, CCPA, and state privacy law obligation mapping
    ai_regulatory_impact        — EU AI Act risk tiers, conformity assessment, FTC AI guidance
    spectrum_licensing_change   — FCC spectrum rulemaking, auction, and build-out obligations
    content_moderation_liability — Section 230, DSA VLOP, NTD, and algorithmic amplification

Technology / Telecom Security Skills:
    cybersecurity_compliance      — CISA KEV, SEC 8-K disclosure, FCC cyber rules, EO 14028
    telecom_infrastructure_security — FCC network security, NTIA broadband, USF, roaming obligations
    data_residency_obligation     — Cross-border data transfer, localisation mandates, SCCs
    tech_merger_review            — FTC/DOJ tech M&A, HSR thresholds, divestiture conditions
    algorithmic_accountability    — EU AI Act, FTC algorithmic scrutiny, bias audit requirements
"""

from naturalsentinel.skills.fetch import FetchFilingsSkill
from naturalsentinel.skills.analyze import AnalyzeFilingSkill
from naturalsentinel.skills.memory_recall import RecallMemorySkill
from naturalsentinel.skills.memory_store import StoreMemorySkill
from naturalsentinel.skills.feedback import RecordFeedbackSkill
from naturalsentinel.skills.context import BuildContextSkill
from naturalsentinel.skills.dedup import DetectDuplicatesSkill
from naturalsentinel.skills.briefing import GenerateBriefingSkill
from naturalsentinel.skills.scan_cycle import ScanCycleSkill
from naturalsentinel.skills.belief_tracker import BeliefTrackerSkill

# Intelligence / analytics skills
from naturalsentinel.skills.alert import AlertThresholdSkill
from naturalsentinel.skills.deadline import ComplianceDeadlineSkill
from naturalsentinel.skills.trends import TrendAnalysisSkill
from naturalsentinel.skills.cross_domain import CrossDomainCorrelationSkill
from naturalsentinel.skills.export_report import ExportReportSkill
from naturalsentinel.skills.regime_detection import RegimeDetectionSkill

# Specialist / desk skills
from naturalsentinel.skills.capital_impact import CapitalImpactSkill
from naturalsentinel.skills.model_risk_assessment import ModelRiskAssessmentSkill
from naturalsentinel.skills.securities_financing import SecuritiesFinancingSkill
from naturalsentinel.skills.liquidity_ratio import LiquidityRatioSkill
from naturalsentinel.skills.agency_mortgage import AgencyMortgageSkill
from naturalsentinel.skills.counterparty_risk import CounterpartyRiskSkill
from naturalsentinel.skills.regulatory_reporting import RegulatoryReportingSkill
from naturalsentinel.skills.optimization_constraint import OptimizationConstraintSkill
from naturalsentinel.skills.leveraged_lending import LeveragedLendingSkill
from naturalsentinel.skills.stress_testing import StressTestingSignalSkill

# Platform / digital regulatory skills
from naturalsentinel.skills.platform_antitrust import PlatformAntitrustSkill
from naturalsentinel.skills.data_privacy import DataPrivacySkill
from naturalsentinel.skills.ai_regulatory import AIRegulatorySkill
from naturalsentinel.skills.spectrum_licensing import SpectrumLicensingSkill
from naturalsentinel.skills.content_moderation import ContentModerationSkill

# Technology / telecom security skills
from naturalsentinel.skills.cybersecurity_compliance import CybersecurityComplianceSkill
from naturalsentinel.skills.telecom_infrastructure import TelecomInfrastructureSkill
from naturalsentinel.skills.data_residency import DataResidencySkill
from naturalsentinel.skills.merger_review import TechMergerReviewSkill
from naturalsentinel.skills.algorithmic_accountability import AlgorithmicAccountabilitySkill

ALL_SKILLS = [
    # Core pipeline
    FetchFilingsSkill(),
    AnalyzeFilingSkill(),
    RecallMemorySkill(),
    StoreMemorySkill(),
    RecordFeedbackSkill(),
    BuildContextSkill(),
    DetectDuplicatesSkill(),
    GenerateBriefingSkill(),
    ScanCycleSkill(),
    BeliefTrackerSkill(),
    # Intelligence / analytics
    AlertThresholdSkill(),
    ComplianceDeadlineSkill(),
    TrendAnalysisSkill(),
    CrossDomainCorrelationSkill(),
    ExportReportSkill(),
    RegimeDetectionSkill(),
    # Specialist / desk
    CapitalImpactSkill(),
    ModelRiskAssessmentSkill(),
    SecuritiesFinancingSkill(),
    LiquidityRatioSkill(),
    AgencyMortgageSkill(),
    CounterpartyRiskSkill(),
    RegulatoryReportingSkill(),
    OptimizationConstraintSkill(),
    LeveragedLendingSkill(),
    StressTestingSignalSkill(),
    # Platform / digital regulatory
    PlatformAntitrustSkill(),
    DataPrivacySkill(),
    AIRegulatorySkill(),
    SpectrumLicensingSkill(),
    ContentModerationSkill(),
    # Technology / telecom security
    CybersecurityComplianceSkill(),
    TelecomInfrastructureSkill(),
    DataResidencySkill(),
    TechMergerReviewSkill(),
    AlgorithmicAccountabilitySkill(),
]

__all__ = [
    "ALL_SKILLS",
    # Core
    "FetchFilingsSkill",
    "AnalyzeFilingSkill",
    "RecallMemorySkill",
    "StoreMemorySkill",
    "RecordFeedbackSkill",
    "BuildContextSkill",
    "DetectDuplicatesSkill",
    "GenerateBriefingSkill",
    "ScanCycleSkill",
    "BeliefTrackerSkill",
    # Intelligence
    "AlertThresholdSkill",
    "ComplianceDeadlineSkill",
    "TrendAnalysisSkill",
    "CrossDomainCorrelationSkill",
    "ExportReportSkill",
    "RegimeDetectionSkill",
    # Specialist / desk
    "CapitalImpactSkill",
    "ModelRiskAssessmentSkill",
    "SecuritiesFinancingSkill",
    "LiquidityRatioSkill",
    "AgencyMortgageSkill",
    "CounterpartyRiskSkill",
    "RegulatoryReportingSkill",
    "OptimizationConstraintSkill",
    "LeveragedLendingSkill",
    "StressTestingSignalSkill",
    # Platform / digital regulatory
    "PlatformAntitrustSkill",
    "DataPrivacySkill",
    "AIRegulatorySkill",
    "SpectrumLicensingSkill",
    "ContentModerationSkill",
    # Technology / telecom security
    "CybersecurityComplianceSkill",
    "TelecomInfrastructureSkill",
    "DataResidencySkill",
    "TechMergerReviewSkill",
    "AlgorithmicAccountabilitySkill",
]
