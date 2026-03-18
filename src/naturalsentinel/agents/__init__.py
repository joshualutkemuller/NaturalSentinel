"""
Specialised agents built on top of the NaturalSentinel skill framework.

Each agent encapsulates a focused domain of responsibility:

    ComplianceTrackerAgent      — tracks deadlines, surfaces overdue obligations,
                                  and generates a structured compliance calendar.

    AlertAgent                  — monitors severity levels in stored analyses and
                                  fires structured alerts when thresholds are exceeded.

    CapitalOptimizationAgent    — RWA / SLR / output floor impact; maps Basel IV and
                                  Fed capital rule changes to optimization model constraints.

    ModelRiskAgent              — SR 11-7 / OCC 2011-12 validation triggers; identifies
                                  models requiring revalidation or challenger development.

    SecuritiesFinancingAgent    — repo, sec lending, TBA margin, SFTR, and rehypothecation
                                  rule changes; prime brokerage and secured lending desks.

    LiquidityRatioAgent         — LCR / NSFR / HQLA classification changes; balance-sheet
                                  optimization constraints for treasury and funding desks.

    AgencyMortgageAgent         — FHFA conforming limits, g-fee adjustments, Agency MBS
                                  haircut and TBA eligibility changes.

    CounterpartyRiskAgent       — SA-CCR supervisory factors, SIMM / UMR, CVA capital;
                                  EAD and XVA recalibration alerts for prime and derivatives.

    RegulatoryReportingAgent    — new / changed reporting obligations, schema updates,
                                  and pipeline build-backlog for data engineering.

    OptimizationConstraintAgent — translates regulatory text into formal constraint
                                  expressions and parameter updates for quant models.

    LeveragedLendingAgent       — OCC / Fed leveraged lending guidance, CLO risk retention,
                                  covenant and threshold changes for secured lending desks.

    StressTestingAgent          — CCAR / DFAST scenario monitoring, macro variable paths,
                                  desk P&L mapping for stress testing and capital planning.

All agents are thin orchestrators that compose AgentRuntime skill invocations
into coherent, high-level workflows.  They do NOT bypass the permission model —
all skill access is still gated by the SecurityPolicy on the underlying runtime.
"""

from naturalsentinel.agents.compliance_tracker import ComplianceTrackerAgent
from naturalsentinel.agents.alert_agent import AlertAgent
from naturalsentinel.agents.capital_optimization_agent import CapitalOptimizationAgent
from naturalsentinel.agents.model_risk_agent import ModelRiskAgent
from naturalsentinel.agents.securities_financing_agent import SecuritiesFinancingAgent
from naturalsentinel.agents.liquidity_ratio_agent import LiquidityRatioAgent
from naturalsentinel.agents.agency_mortgage_agent import AgencyMortgageAgent
from naturalsentinel.agents.counterparty_risk_agent import CounterpartyRiskAgent
from naturalsentinel.agents.regulatory_reporting_agent import RegulatoryReportingAgent
from naturalsentinel.agents.optimization_constraint_agent import OptimizationConstraintAgent
from naturalsentinel.agents.leveraged_lending_agent import LeveragedLendingAgent
from naturalsentinel.agents.stress_testing_agent import StressTestingAgent

__all__ = [
    "ComplianceTrackerAgent",
    "AlertAgent",
    "CapitalOptimizationAgent",
    "ModelRiskAgent",
    "SecuritiesFinancingAgent",
    "LiquidityRatioAgent",
    "AgencyMortgageAgent",
    "CounterpartyRiskAgent",
    "RegulatoryReportingAgent",
    "OptimizationConstraintAgent",
    "LeveragedLendingAgent",
    "StressTestingAgent",
]
