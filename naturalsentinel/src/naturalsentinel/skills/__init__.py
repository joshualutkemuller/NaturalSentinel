"""
Built-in skill library for NaturalSentinel.

Each skill is a self-contained capability with declared permissions,
input/output schemas, and dependency graphs.

Skills:
    fetch_filings      — Retrieve regulatory filings from sources
    analyze_filing     — LLM-powered impact analysis of a single filing
    recall_memory      — Semantic search across persistent memory
    store_memory       — Persist analysis results to memory
    record_feedback    — Record human corrections as precedent memory
    build_context      — Assemble memory context for LLM prompts
    detect_duplicates  — Check filings against seen-state
    generate_briefing  — Produce executive-level regulatory briefing
    scan_cycle         — Full orchestrated scan (composes other skills)
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

ALL_SKILLS = [
    FetchFilingsSkill(),
    AnalyzeFilingSkill(),
    RecallMemorySkill(),
    StoreMemorySkill(),
    RecordFeedbackSkill(),
    BuildContextSkill(),
    DetectDuplicatesSkill(),
    GenerateBriefingSkill(),
    ScanCycleSkill(),
]

__all__ = [
    "ALL_SKILLS",
    "FetchFilingsSkill",
    "AnalyzeFilingSkill",
    "RecallMemorySkill",
    "StoreMemorySkill",
    "RecordFeedbackSkill",
    "BuildContextSkill",
    "DetectDuplicatesSkill",
    "GenerateBriefingSkill",
    "ScanCycleSkill",
]
