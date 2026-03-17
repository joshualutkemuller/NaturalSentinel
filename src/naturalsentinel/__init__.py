"""
NaturalSentinel — Agentic Regulatory Change Monitor
====================================================

Monitors regulatory filings (SEC, CFPB, Fed, FDA, EPA, USTR), parses
dense legal/regulatory language, maps changes to affected business lines,
and learns from human feedback through persistent memory.

Quick start::

    from naturalsentinel import RegulatoryMonitorAgent, MockProvider, MemoryStore

    memory = MemoryStore(":memory:")
    agent = RegulatoryMonitorAgent(MockProvider(), memory=memory)
    results = agent.run(since_days=90)
"""

__version__ = "0.1.0"

from naturalsentinel.models import (
    ChangeType,
    ImpactAssessment,
    MonitorResult,
    RegulatoryDomain,
    RegulatoryFiling,
    Severity,
)
from naturalsentinel.agent import RegulatoryMonitorAgent
from naturalsentinel.providers.base import ModelProvider
from naturalsentinel.providers.mock import MockProvider
from naturalsentinel.memory.store import MemoryStore
from naturalsentinel.memory.types import MemoryRecord, MemoryType

__all__ = [
    "RegulatoryMonitorAgent",
    "ModelProvider",
    "MockProvider",
    "MemoryStore",
    "MemoryRecord",
    "MemoryType",
    "RegulatoryDomain",
    "RegulatoryFiling",
    "ImpactAssessment",
    "MonitorResult",
    "Severity",
    "ChangeType",
]
