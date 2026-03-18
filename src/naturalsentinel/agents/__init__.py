"""
Specialised agents built on top of the NaturalSentinel skill framework.

Each agent encapsulates a focused domain of responsibility:

    ComplianceTrackerAgent  — tracks deadlines, surfaces overdue obligations,
                              and generates a structured compliance calendar.

    AlertAgent              — monitors severity levels in stored analyses and
                              fires structured alerts when thresholds are exceeded.

Both agents are thin orchestrators that compose AgentRuntime skill invocations
into coherent, high-level workflows.  They do NOT bypass the permission model —
all skill access is still gated by the SecurityPolicy on the underlying runtime.
"""

from naturalsentinel.agents.compliance_tracker import ComplianceTrackerAgent
from naturalsentinel.agents.alert_agent import AlertAgent

__all__ = ["ComplianceTrackerAgent", "AlertAgent"]
