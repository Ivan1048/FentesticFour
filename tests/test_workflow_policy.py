"""Minimal tests for DSR calculations and loan policy rules."""

from __future__ import annotations

import pytest

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.tools.dsr import (
    assess_affordability,
    calculate_dsr,
    calculate_monthly_installment,
)
from backend.tools.policy import identify_missing_fields, make_decision
from backend.schemas import (
    AnalysisResult,
    ExtractedFields,
    LoanStatus,
    RiskLevel,
    ToolResults,
)


# ================================================================ DSR Tests ===

class TestCalculateMonthlyInstallment:
    def test_positive_loan_amount(self):
        installment = calculate_monthly_installment(300_000, 360, 0.08)
        assert 2000 < installment < 2500, f"Expected ~RM 2,201 but got {installment:.2f}"

    def test_zero_interest_rate(self):
        installment = calculate_monthly_installment(120_000, 120, annual_rate=0)
        assert abs(installment - 1000) < 0.01

    def test_short_term(self):
        installment = calculate_monthly_installment(50_000, 12, 0.0)
        assert abs(installment - 50_000 / 12) < 0.01


class TestCalculateDSR:
    def test_no_debts(self):
        installment = calculate_monthly_installment(200_000, 240, 0.08)
        dsr = calculate_dsr(10_000, 0, installment)
        assert 0 < dsr < 100

    def test_zero_income_returns_100(self):
        assert calculate_dsr(0, 500, 1000) == 100.0

    def test_typical_eligible(self):
        # RM 8,000 income, RM 500 debts, RM 1,000 installment → DSR = 18.75%
        dsr = calculate_dsr(8_000, 500, 1_000)
        assert abs(dsr - 18.75) < 0.01

    def test_typical_medium_risk(self):
        # RM 5,000 income, RM 1,000 debts, RM 1,500 installment → DSR = 50%
        dsr = calculate_dsr(5_000, 1_000, 1_500)
        assert abs(dsr - 50.0) < 0.01

    def test_high_risk(self):
        # RM 3,000 income, RM 1,000 debts, RM 1,500 installment → DSR = 83.3%
        dsr = calculate_dsr(3_000, 1_000, 1_500)
        assert dsr > 60


class TestAssessAffordability:
    def test_low_risk(self):
        result = assess_affordability(35.0)
        assert result["risk_level"] == "low"
        assert result["eligible"] is True

    def test_medium_risk(self):
        result = assess_affordability(50.0)
        assert result["risk_level"] == "medium"
        assert result["eligible"] is True

    def test_high_risk(self):
        result = assess_affordability(65.0)
        assert result["risk_level"] == "high"
        assert result["eligible"] is False

    def test_boundary_40_is_medium(self):
        result = assess_affordability(40.0)
        assert result["risk_level"] == "medium"

    def test_boundary_60_is_high(self):
        result = assess_affordability(60.0)
        assert result["risk_level"] == "high"

    def test_boundary_just_below_40(self):
        result = assess_affordability(39.9)
        assert result["risk_level"] == "low"


# ============================================================== Policy Tests ===

def _full_fields(**overrides) -> ExtractedFields:
    defaults = dict(
        applicant_name="Ahmad Zaki",
        monthly_income=8000.0,
        monthly_debts=500.0,
        employment_status="employed",
        loan_type="home",
        loan_amount=300_000.0,
        loan_term_months=360,
    )
    defaults.update(overrides)
    return ExtractedFields(**defaults)


class TestIdentifyMissingFields:
    def test_no_missing_when_complete(self):
        fields = _full_fields()
        assert identify_missing_fields(fields) == []

    def test_detects_missing_income(self):
        fields = _full_fields(monthly_income=None)
        missing = identify_missing_fields(fields)
        assert any("income" in m.lower() for m in missing)

    def test_detects_missing_name(self):
        fields = _full_fields(applicant_name=None)
        missing = identify_missing_fields(fields)
        assert any("name" in m.lower() for m in missing)

    def test_detects_multiple_missing(self):
        fields = ExtractedFields()  # all None
        missing = identify_missing_fields(fields)
        assert len(missing) >= 5


class TestMakeDecision:
    def _analysis(self, dsr: float, risk: str) -> AnalysisResult:
        return AnalysisResult(
            dsr=dsr,
            estimated_monthly_installment=1500.0,
            risk_level=RiskLevel(risk),
        )

    def test_approved_for_low_risk(self):
        fields = _full_fields()
        analysis = self._analysis(30.0, "low")
        decision = make_decision(fields, analysis, ToolResults())
        assert decision.loan_status == LoanStatus.APPROVED
        assert decision.risk_level == RiskLevel.LOW

    def test_manual_review_for_medium_risk(self):
        fields = _full_fields()
        analysis = self._analysis(50.0, "medium")
        decision = make_decision(fields, analysis, ToolResults())
        assert decision.loan_status == LoanStatus.MANUAL_REVIEW
        assert decision.risk_level == RiskLevel.MEDIUM

    def test_rejected_for_high_risk(self):
        fields = _full_fields()
        analysis = self._analysis(75.0, "high")
        decision = make_decision(fields, analysis, ToolResults())
        assert decision.loan_status == LoanStatus.REJECTED
        assert decision.risk_level == RiskLevel.HIGH

    def test_incomplete_when_fields_missing(self):
        fields = ExtractedFields()  # no fields
        decision = make_decision(fields, AnalysisResult(), ToolResults())
        assert decision.loan_status == LoanStatus.INCOMPLETE
        assert len(decision.missing_information) > 0

    def test_manual_review_on_credit_failure(self):
        fields = _full_fields()
        analysis = self._analysis(30.0, "low")
        tool = ToolResults(credit_check_failed=True)
        decision = make_decision(fields, analysis, tool)
        assert decision.loan_status == LoanStatus.MANUAL_REVIEW

    def test_dsr_included_in_decision(self):
        fields = _full_fields()
        analysis = self._analysis(35.5, "low")
        decision = make_decision(fields, analysis, ToolResults())
        assert "35.5%" in (decision.dsr or "")
