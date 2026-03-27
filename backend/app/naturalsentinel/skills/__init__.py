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
    run_evaluation      — Quantitative extraction accuracy, calibration, and drift

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

from app.naturalsentinel.skills.agency_mortgage import AgencyMortgageSkill
from app.naturalsentinel.skills.ai_regulatory import AIRegulatorySkill

# Intelligence / analytics skills
from app.naturalsentinel.skills.alert import AlertThresholdSkill
from app.naturalsentinel.skills.algorithmic_accountability import (
    AlgorithmicAccountabilitySkill,
)
from app.naturalsentinel.skills.analyze import AnalyzeFilingSkill
from app.naturalsentinel.skills.belief_tracker import BeliefTrackerSkill
from app.naturalsentinel.skills.briefing import GenerateBriefingSkill

# Specialist / desk skills
from app.naturalsentinel.skills.capital_impact import CapitalImpactSkill
from app.naturalsentinel.skills.content_moderation import ContentModerationSkill
from app.naturalsentinel.skills.context import BuildContextSkill
from app.naturalsentinel.skills.counterparty_risk import CounterpartyRiskSkill
from app.naturalsentinel.skills.cross_domain import CrossDomainCorrelationSkill

# Technology / telecom security skills
from app.naturalsentinel.skills.cybersecurity_compliance import (
    CybersecurityComplianceSkill,
)
from app.naturalsentinel.skills.data_privacy import DataPrivacySkill
from app.naturalsentinel.skills.data_residency import DataResidencySkill
from app.naturalsentinel.skills.deadline import ComplianceDeadlineSkill
from app.naturalsentinel.skills.dedup import DetectDuplicatesSkill
from app.naturalsentinel.skills.export_report import ExportReportSkill
from app.naturalsentinel.skills.feedback import RecordFeedbackSkill
from app.naturalsentinel.skills.fetch import FetchFilingsSkill
from app.naturalsentinel.skills.leveraged_lending import LeveragedLendingSkill
from app.naturalsentinel.skills.liquidity_ratio import LiquidityRatioSkill
from app.naturalsentinel.skills.memory_recall import RecallMemorySkill
from app.naturalsentinel.skills.memory_store import StoreMemorySkill
from app.naturalsentinel.skills.merger_review import TechMergerReviewSkill
from app.naturalsentinel.skills.model_risk_assessment import ModelRiskAssessmentSkill
from app.naturalsentinel.skills.optimization_constraint import (
    OptimizationConstraintSkill,
)

# Platform / digital regulatory skills
from app.naturalsentinel.skills.platform_antitrust import PlatformAntitrustSkill
from app.naturalsentinel.skills.regime_detection import RegimeDetectionSkill
from app.naturalsentinel.skills.regulatory_reporting import RegulatoryReportingSkill
from app.naturalsentinel.skills.run_evaluation import RunEvaluationSkill
from app.naturalsentinel.skills.scan_cycle import ScanCycleSkill
from app.naturalsentinel.skills.securities_financing import SecuritiesFinancingSkill
from app.naturalsentinel.skills.spectrum_licensing import SpectrumLicensingSkill
from app.naturalsentinel.skills.stress_testing import StressTestingSignalSkill
from app.naturalsentinel.skills.telecom_infrastructure import TelecomInfrastructureSkill
from app.naturalsentinel.skills.trends import TrendAnalysisSkill

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
    RunEvaluationSkill(),
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
    "RunEvaluationSkill",
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
