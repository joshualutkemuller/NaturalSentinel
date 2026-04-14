"""
Built-in skill library for NaturalSentinel.

Each skill is a self-contained capability with declared permissions,
input/output schemas, and dependency graphs. Phase R grouped the 40
skill modules into 7 topical subpackages for navigability:

    core/             — orchestration / framework (scan_cycle, fetch,
                        dedup, analyze, briefing, alert, context,
                        feedback, memory_store, memory_recall)
    documents/        — document intelligence (ingest_document,
                        recall_context, follow_process)
    financial/        — financial-services domain (leveraged_lending,
                        liquidity_ratio, capital_impact, stress_testing,
                        counterparty_risk, securities_financing,
                        merger_review, agency_mortgage,
                        regulatory_reporting)
    governance/       — AI / model risk (ai_regulatory,
                        algorithmic_accountability,
                        model_risk_assessment, belief_tracker,
                        content_moderation)
    privacy_security/ — privacy + security (cybersecurity_compliance,
                        data_privacy, data_residency)
    operations/       — cross-domain monitoring (deadline, trends,
                        cross_domain, regime_detection,
                        platform_antitrust, optimization_constraint,
                        spectrum_licensing, telecom_infrastructure)
    reporting/        — reporting and evaluation (export_report,
                        run_evaluation)

``ALL_SKILLS`` re-exports every instance so existing callers keep
working. In Phase P2.2 this hand-maintained list will be replaced by a
``@register_skill`` decorator-driven auto-discovery mechanism.
"""

# ── core / orchestration ───────────────────────────────────────────────
from app.naturalsentinel.skills.core.alert import AlertThresholdSkill
from app.naturalsentinel.skills.core.analyze import AnalyzeFilingSkill
from app.naturalsentinel.skills.core.briefing import GenerateBriefingSkill
from app.naturalsentinel.skills.core.context import BuildContextSkill
from app.naturalsentinel.skills.core.dedup import DetectDuplicatesSkill
from app.naturalsentinel.skills.core.feedback import RecordFeedbackSkill
from app.naturalsentinel.skills.core.fetch import FetchFilingsSkill
from app.naturalsentinel.skills.core.memory_recall import RecallMemorySkill
from app.naturalsentinel.skills.core.memory_store import StoreMemorySkill
from app.naturalsentinel.skills.core.scan_cycle import ScanCycleSkill

# ── documents / document intelligence ──────────────────────────────────
from app.naturalsentinel.skills.documents.follow_process import FollowProcessSkill
from app.naturalsentinel.skills.documents.ingest_document import IngestDocumentSkill
from app.naturalsentinel.skills.documents.recall_context import RecallContextSkill

# ── financial / portfolio-level skills ─────────────────────────────────
from app.naturalsentinel.skills.financial.agency_mortgage import AgencyMortgageSkill
from app.naturalsentinel.skills.financial.capital_impact import CapitalImpactSkill
from app.naturalsentinel.skills.financial.counterparty_risk import CounterpartyRiskSkill
from app.naturalsentinel.skills.financial.leveraged_lending import LeveragedLendingSkill
from app.naturalsentinel.skills.financial.liquidity_ratio import LiquidityRatioSkill
from app.naturalsentinel.skills.financial.merger_review import TechMergerReviewSkill
from app.naturalsentinel.skills.financial.regulatory_reporting import (
    RegulatoryReportingSkill,
)
from app.naturalsentinel.skills.financial.securities_financing import (
    SecuritiesFinancingSkill,
)
from app.naturalsentinel.skills.financial.stress_testing import StressTestingSignalSkill

# ── governance / AI / model risk ───────────────────────────────────────
from app.naturalsentinel.skills.governance.ai_regulatory import AIRegulatorySkill
from app.naturalsentinel.skills.governance.algorithmic_accountability import (
    AlgorithmicAccountabilitySkill,
)
from app.naturalsentinel.skills.governance.belief_tracker import BeliefTrackerSkill
from app.naturalsentinel.skills.governance.content_moderation import (
    ContentModerationSkill,
)
from app.naturalsentinel.skills.governance.model_risk_assessment import (
    ModelRiskAssessmentSkill,
)

# ── operations / cross-domain monitoring ───────────────────────────────
from app.naturalsentinel.skills.operations.cross_domain import (
    CrossDomainCorrelationSkill,
)
from app.naturalsentinel.skills.operations.deadline import ComplianceDeadlineSkill
from app.naturalsentinel.skills.operations.optimization_constraint import (
    OptimizationConstraintSkill,
)
from app.naturalsentinel.skills.operations.platform_antitrust import (
    PlatformAntitrustSkill,
)
from app.naturalsentinel.skills.operations.regime_detection import RegimeDetectionSkill
from app.naturalsentinel.skills.operations.spectrum_licensing import (
    SpectrumLicensingSkill,
)
from app.naturalsentinel.skills.operations.telecom_infrastructure import (
    TelecomInfrastructureSkill,
)
from app.naturalsentinel.skills.operations.trends import TrendAnalysisSkill

# ── privacy and security ───────────────────────────────────────────────
from app.naturalsentinel.skills.privacy_security.cybersecurity_compliance import (
    CybersecurityComplianceSkill,
)
from app.naturalsentinel.skills.privacy_security.data_privacy import DataPrivacySkill
from app.naturalsentinel.skills.privacy_security.data_residency import (
    DataResidencySkill,
)

# ── reporting and evaluation ───────────────────────────────────────────
from app.naturalsentinel.skills.reporting.export_report import ExportReportSkill
from app.naturalsentinel.skills.reporting.run_evaluation import RunEvaluationSkill

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
    # Document Intelligence
    IngestDocumentSkill(),
    RecallContextSkill(),
    FollowProcessSkill(),
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
    # Document Intelligence
    "IngestDocumentSkill",
    "RecallContextSkill",
    "FollowProcessSkill",
]
