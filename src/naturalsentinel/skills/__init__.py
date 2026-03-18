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

Intelligence Skills:
    alert_threshold          — Flag analyses breaching severity thresholds
    compliance_deadline      — Extract and prioritise compliance deadlines
    trend_analysis           — Detect regulatory escalation patterns over time
    cross_domain_correlation — Find business-line overlaps across agencies
    export_report            — Render compliance reports (markdown/json/csv)

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

# Intelligence / analytics skills
from naturalsentinel.skills.alert import AlertThresholdSkill
from naturalsentinel.skills.deadline import ComplianceDeadlineSkill
from naturalsentinel.skills.trends import TrendAnalysisSkill
from naturalsentinel.skills.cross_domain import CrossDomainCorrelationSkill
from naturalsentinel.skills.export_report import ExportReportSkill

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
    # Intelligence / analytics
    AlertThresholdSkill(),
    ComplianceDeadlineSkill(),
    TrendAnalysisSkill(),
    CrossDomainCorrelationSkill(),
    ExportReportSkill(),
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
    # Intelligence
    "AlertThresholdSkill",
    "ComplianceDeadlineSkill",
    "TrendAnalysisSkill",
    "CrossDomainCorrelationSkill",
    "ExportReportSkill",
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
]
