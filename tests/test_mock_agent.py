"""Integration tests for MockAgentClient."""

from __future__ import annotations

import asyncio
import pytest

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent.mock import MockAgentClient


@pytest.fixture
def agent():
    return MockAgentClient()


class TestMockIntakeAgent:
    def test_extracts_monthly_income(self, agent):
        result = asyncio.get_event_loop().run_until_complete(
            agent.intake(
                "I earn RM 8000 per month and want a home loan",
                [],
                {},
            )
        )
        fields = result["extracted_fields"]
        assert fields.get("monthly_income") == 8000.0

    def test_extracts_loan_type(self, agent):
        result = asyncio.get_event_loop().run_until_complete(
            agent.intake("I need a home loan of RM 300000 for 30 years", [], {})
        )
        fields = result["extracted_fields"]
        assert fields.get("loan_type") == "home"

    def test_extracts_loan_term_from_years(self, agent):
        result = asyncio.get_event_loop().run_until_complete(
            agent.intake("I want a 25 year loan", [], {})
        )
        fields = result["extracted_fields"]
        assert fields.get("loan_term_months") == 300

    def test_missing_fields_prompted(self, agent):
        result = asyncio.get_event_loop().run_until_complete(
            agent.intake("Hello, I want a loan", [], {})
        )
        assert len(result["missing_fields"]) > 0
        assert result["assistant_message"]

    def test_no_missing_when_all_provided(self, agent):
        complete = {
            "applicant_name": "Ahmad",
            "monthly_income": 8000.0,
            "monthly_debts": 500.0,
            "employment_status": "employed",
            "loan_type": "home",
            "loan_amount": 300_000.0,
            "loan_term_months": 360,
        }
        result = asyncio.get_event_loop().run_until_complete(
            agent.intake("All info already provided", [], complete)
        )
        assert result["missing_fields"] == []


class TestMockUnderwriterAgent:
    def test_returns_assessment(self, agent):
        result = asyncio.get_event_loop().run_until_complete(
            agent.underwriter(
                {"employment_status": "employed"},
                {"dsr": 35.0, "risk_level": "low", "estimated_monthly_installment": 1500},
            )
        )
        assert "assessment_summary" in result
        assert isinstance(result["risk_flags"], list)

    def test_flags_high_dsr(self, agent):
        result = asyncio.get_event_loop().run_until_complete(
            agent.underwriter({}, {"dsr": 70.0, "risk_level": "high"})
        )
        assert any("60%" in flag or "high" in flag.lower() for flag in result["risk_flags"])


class TestMockVerificationAgent:
    def test_credit_failure_flagged(self, agent):
        result = asyncio.get_event_loop().run_until_complete(
            agent.verification(
                {},
                {"credit_check_failed": True, "credit_score": None},
            )
        )
        assert any("credit" in f.lower() for f in result["flags"])

    def test_good_credit_no_flags(self, agent):
        result = asyncio.get_event_loop().run_until_complete(
            agent.verification(
                {},
                {"credit_score": 750, "credit_band": "Excellent", "credit_check_failed": False},
            )
        )
        assert result["verification_summary"]
        assert not any("failed" in f.lower() for f in result["flags"])


class TestMockCommsAgent:
    def test_approved_message(self, agent):
        msg = asyncio.get_event_loop().run_until_complete(
            agent.comms({"loan_status": "approved", "dsr": "35.0%", "next_action": "Proceed", "missing_information": [], "risk_level": "low"}, "Ahmad")
        )
        assert "Ahmad" in msg
        assert "approved" in msg.lower()

    def test_rejected_message(self, agent):
        msg = asyncio.get_event_loop().run_until_complete(
            agent.comms({"loan_status": "rejected", "dsr": "70.0%", "next_action": "Reapply", "missing_information": [], "risk_level": "high"}, "Siti")
        )
        assert "Siti" in msg
        assert "declined" in msg.lower() or "rejected" in msg.lower()
