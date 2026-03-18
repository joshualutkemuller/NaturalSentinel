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
]
