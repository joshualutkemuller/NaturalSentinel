"""
NaturalSentinel — Agentic Regulatory Change Monitor
====================================================

Monitors regulatory filings (SEC, CFPB, Fed, FDA, EPA, USTR), parses
dense legal/regulatory language, maps changes to affected business lines,
and learns from human feedback through persistent memory.

Preferred runtime (strategic direction)::

    from naturalsentinel import AgentRuntime, MockProvider, MemoryStore
    from naturalsentinel.skills import ALL_SKILLS

    runtime = AgentRuntime(provider=MockProvider(), memory=MemoryStore(":memory:"))
    runtime.register_skills(*ALL_SKILLS)
    result = runtime.execute_skill("scan_cycle", {"since_days": 90})

Compatibility layer (legacy monitor)::

    from naturalsentinel import RegulatoryMonitorAgent, MockProvider, MemoryStore

    memory = MemoryStore(":memory:")
    agent = RegulatoryMonitorAgent(MockProvider(), memory=memory)
    results = agent.run(since_days=90)
"""

__version__ = "0.1.0"

from naturalsentinel.agent import RegulatoryMonitorAgent
from naturalsentinel.agent_framework import (
    FULL,
    READONLY,
    STANDARD,
    AgentRuntime,
    AuditLog,
    ExecutionPlan,
    LatencyClass,
    Permission,
    PlanStep,
    SecurityPolicy,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillRegistry,
    SkillResult,
)
from naturalsentinel.evidence import EvidenceLedgerEntry
from naturalsentinel.memory.store import MemoryStore
from naturalsentinel.memory.types import MemoryRecord, MemoryType
from naturalsentinel.models import (
    ChangeType,
    DecisionFrame,
    ImpactAssessment,
    MonitorResult,
    RegulatoryDomain,
    RegulatoryFiling,
    Severity,
)
from naturalsentinel.providers.base import ModelProvider
from naturalsentinel.providers.mock import MockProvider

__all__ = [
    # Legacy agent
    "RegulatoryMonitorAgent",
    # Framework
    "AgentRuntime",
    "AuditLog",
    "ExecutionPlan",
    "LatencyClass",
    "Permission",
    "PlanStep",
    "SecurityPolicy",
    "Skill",
    "SkillContext",
    "SkillMetadata",
    "SkillParameter",
    "SkillRegistry",
    "SkillResult",
    "READONLY",
    "STANDARD",
    "FULL",
    # Providers
    "ModelProvider",
    "MockProvider",
    # Memory
    "MemoryStore",
    "MemoryRecord",
    "MemoryType",
    "EvidenceLedgerEntry",
    # Models
    "RegulatoryDomain",
    "RegulatoryFiling",
    "ImpactAssessment",
    "DecisionFrame",
    "MonitorResult",
    "Severity",
    "ChangeType",
]
