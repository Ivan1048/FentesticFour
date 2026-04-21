"""Simulated external property valuation tool."""

from __future__ import annotations

from typing import Dict, Optional


def get_property_valuation(
    property_address: Optional[str],
    provided_value: Optional[float] = None,
    simulate_failure: bool = False,
) -> Dict:
    """
    Simulate a property valuation service.

    Returns:
        {
            "valuation": float | None,
            "failed": bool,
            "message": str,
            "ltv": float | None,  # loan-to-value ratio if loan_amount provided
        }
    """
    if simulate_failure:
        return {
            "valuation": None,
            "failed": True,
            "message": "Property valuation service unavailable. Manual appraisal required.",
        }

    if not property_address:
        return {
            "valuation": provided_value,
            "failed": False,
            "message": "No property address provided; using applicant-declared value." if provided_value else "No property address or value provided.",
        }

    # Simulate valuation as ±10% of provided value or a base estimate
    if provided_value:
        # Simulate independent appraisal slightly different from stated value
        seed = sum(ord(c) for c in property_address.lower()) % 100
        adjustment = (seed - 50) / 1000  # -5% to +4.9%
        valuation = provided_value * (1 + adjustment)
    else:
        # Generate a plausible value based on address hash
        seed = sum(ord(c) for c in property_address.lower())
        valuation = 150_000 + (seed % 350_000)

    return {
        "valuation": round(valuation, 2),
        "failed": False,
        "message": f"Property valuation completed: {valuation:,.2f}.",
    }
