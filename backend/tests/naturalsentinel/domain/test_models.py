"""Tests for naturalsentinel.models — domain types and dataclasses."""

from app.naturalsentinel.models import (
    ChangeType,
    DecisionFrame,
    ImpactAssessment,
    RegulatoryDomain,
    RegulatoryFiling,
    Severity,
)


class TestEnums:
    def test_regulatory_domain_values(self):
        assert RegulatoryDomain.SEC.value == "sec"
        assert RegulatoryDomain.FDA.value == "fda"
        assert len(RegulatoryDomain) >= 6

    def test_severity_ordering(self):
        severities = [s.value for s in Severity]
        assert severities == ["low", "medium", "high", "critical"]

    def test_change_type_roundtrip(self):
        for ct in ChangeType:
            assert ChangeType(ct.value) is ct

    def test_domain_from_string(self):
        assert RegulatoryDomain("cfpb") is RegulatoryDomain.CFPB


class TestRegulatoryFiling:
    def test_creation_defaults(self):
        f = RegulatoryFiling(
            id="TEST-001",
            title="Test Filing",
            domain=RegulatoryDomain.SEC,
            source_url="https://example.com",
            published_date="2026-01-01",
            raw_text="Some regulatory text.",
        )
        assert f.change_type == ChangeType.NOTICE
        assert f.summary == ""
        assert f.fetched_at  # auto-generated

    def test_creation_with_overrides(self):
        f = RegulatoryFiling(
            id="TEST-002",
            title="Test",
            domain=RegulatoryDomain.FDA,
            source_url="https://example.com",
            published_date="2026-01-01",
            raw_text="Text",
            change_type=ChangeType.FINAL_RULE,
            summary="A summary.",
        )
        assert f.change_type == ChangeType.FINAL_RULE
        assert f.summary == "A summary."


class TestImpactAssessment:
    def test_creation(self):
        ia = ImpactAssessment(
            filing_id="TEST-001",
            severity=Severity.HIGH,
            affected_business_lines=["Consumer Lending"],
            affected_regulations=["ECOA"],
            compliance_deadline="2026-12-31",
            action_items=["[Legal] Review policies"],
            risk_summary="Risk is high.",
            confidence=0.85,
        )
        assert ia.severity == Severity.HIGH
        assert ia.confidence == 0.85
        assert len(ia.action_items) == 1


class TestDecisionFrame:
    def test_creation_defaults(self):
        decision = DecisionFrame(
            decision_id="decision::TEST-001",
            question="What response is warranted?",
            scope="SEC filing review",
            time_horizon="near-term",
        )
        assert decision.owner == "Unassigned"
        assert decision.candidate_actions == []
        assert decision.audit_refs == []
