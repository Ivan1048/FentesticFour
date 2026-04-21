"""Deterministic DSR (Debt-Service Ratio) calculations and affordability checks."""

from __future__ import annotations

from typing import Optional


ANNUAL_INTEREST_RATE = 0.08  # 8% default assumption


def calculate_monthly_installment(
    loan_amount: float, loan_term_months: int, annual_rate: float = ANNUAL_INTEREST_RATE
) -> float:
    """Calculate monthly mortgage/loan installment using standard amortisation formula."""
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        return loan_amount / loan_term_months
    numerator = loan_amount * monthly_rate * (1 + monthly_rate) ** loan_term_months
    denominator = (1 + monthly_rate) ** loan_term_months - 1
    return numerator / denominator


def calculate_dsr(
    monthly_income: float,
    existing_monthly_debts: float,
    new_monthly_installment: float,
) -> float:
    """
    Calculate Debt-Service Ratio as a percentage.

    DSR = (total monthly debt obligations / gross monthly income) * 100
    """
    if monthly_income <= 0:
        return 100.0
    total_obligations = existing_monthly_debts + new_monthly_installment
    return (total_obligations / monthly_income) * 100


def assess_affordability(dsr: float) -> dict:
    """
    Assess affordability based on DSR thresholds.

    - DSR < 40%: eligible (low risk)
    - 40% <= DSR < 60%: medium risk
    - DSR >= 60%: high risk (reject / manual review)
    """
    if dsr < 40:
        return {"risk_level": "low", "eligible": True, "message": "DSR is within acceptable range."}
    elif dsr < 60:
        return {
            "risk_level": "medium",
            "eligible": True,
            "message": "DSR is elevated; medium-risk loan may require additional conditions.",
        }
    else:
        return {
            "risk_level": "high",
            "eligible": False,
            "message": "DSR exceeds 60%; application is high-risk and flagged for rejection or manual review.",
        }


def affordability_ratio(
    monthly_income: float,
    loan_amount: float,
    loan_term_months: int,
    annual_rate: float = ANNUAL_INTEREST_RATE,
) -> Optional[float]:
    """Return monthly installment as a ratio of income (0-1 scale)."""
    if monthly_income <= 0:
        return None
    installment = calculate_monthly_installment(loan_amount, loan_term_months, annual_rate)
    return installment / monthly_income
