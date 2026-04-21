"""Simulated external credit score check tool."""

from __future__ import annotations

import random
from typing import Dict


CREDIT_BANDS = [
    (750, "Excellent"),
    (700, "Good"),
    (650, "Fair"),
    (600, "Poor"),
    (0, "Very Poor"),
]


def get_credit_band(score: int) -> str:
    for threshold, label in CREDIT_BANDS:
        if score >= threshold:
            return label
    return "Very Poor"


def check_credit_score(
    applicant_name: str,
    simulate_failure: bool = False,
) -> Dict:
    """
    Simulate a credit bureau lookup.

    Returns:
        {
            "score": int,
            "band": str,
            "failed": bool,
            "message": str,
        }
    """
    if simulate_failure:
        return {
            "score": None,
            "band": None,
            "failed": True,
            "message": "Credit bureau service temporarily unavailable. Application flagged for manual review.",
        }

    # Deterministic-ish score based on name hash so re-runs are consistent
    seed = sum(ord(c) for c in applicant_name.lower()) % 200
    score = 600 + seed  # Range: 600–799
    band = get_credit_band(score)
    return {
        "score": score,
        "band": band,
        "failed": False,
        "message": f"Credit score retrieved successfully: {score} ({band}).",
    }
