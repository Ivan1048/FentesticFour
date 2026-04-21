"""Loan decision policy rules."""

from __future__ import annotations

from typing import List

from ..schemas import (
    AnalysisResult,
    DecisionOutput,
    ExtractedFields,
    LoanStatus,
    RiskLevel,
    ToolResults,
)


REQUIRED_FIELDS = [
    ("applicant_name", "Applicant full name"),
    ("monthly_income", "Monthly gross income"),
    ("monthly_debts", "Existing monthly debt obligations"),
    ("employment_status", "Employment status"),
    ("loan_type", "Type of loan (e.g., home, personal, auto)"),
    ("loan_amount", "Requested loan amount"),
    ("loan_term_months", "Loan term in months"),
]


def identify_missing_fields(fields: ExtractedFields) -> List[str]:
    """Return a list of human-readable missing field descriptions."""
    missing = []
    for attr, label in REQUIRED_FIELDS:
        if getattr(fields, attr) is None:
            missing.append(label)
    return missing


def make_decision(
    fields: ExtractedFields,
    analysis: AnalysisResult,
    tool_results: ToolResults,
) -> DecisionOutput:
    """Apply decision rules and return a structured DecisionOutput."""
    missing = identify_missing_fields(fields)

    if missing:
        return DecisionOutput(
            loan_status=LoanStatus.INCOMPLETE,
            risk_level=RiskLevel.UNKNOWN,
            dsr=None,
            missing_information=missing,
            next_action="Please provide the missing information listed above.",
        )

    dsr_str = f"{analysis.dsr:.1f}%" if analysis.dsr is not None else "N/A"

    # Reject if credit check has failed (simulate hard stop)
    if tool_results.credit_check_failed:
        return DecisionOutput(
            loan_status=LoanStatus.MANUAL_REVIEW,
            risk_level=RiskLevel.UNKNOWN,
            dsr=dsr_str,
            missing_information=[],
            next_action="Credit bureau check failed; application escalated for manual review.",
        )

    risk = analysis.risk_level

    if risk == RiskLevel.HIGH:
        return DecisionOutput(
            loan_status=LoanStatus.REJECTED,
            risk_level=risk,
            dsr=dsr_str,
            missing_information=[],
            next_action="Loan rejected due to high DSR. Applicant may reapply with a smaller loan or higher income.",
        )
    elif risk == RiskLevel.MEDIUM:
        return DecisionOutput(
            loan_status=LoanStatus.MANUAL_REVIEW,
            risk_level=risk,
            dsr=dsr_str,
            missing_information=[],
            next_action="Application forwarded for manual underwriter review due to medium-risk DSR.",
        )
    else:
        return DecisionOutput(
            loan_status=LoanStatus.APPROVED,
            risk_level=risk,
            dsr=dsr_str,
            missing_information=[],
            next_action="Loan approved. Proceed to documentation and disbursement.",
        )
