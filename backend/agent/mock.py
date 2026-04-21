"""Mock AgentClient – deterministic responses for demo/testing."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .base import AgentClient


_FIELD_PATTERNS = {
    "applicant_name": [
        r"(?:my name is|i am|name[:\s]+)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
    ],
    "monthly_income": [
        r"(?:earn|income|salary|make)[^\d]*(?:RM\s?)?(\d[\d,]*(?:\.\d+)?)",
        r"(?:RM|rm)\s?(\d[\d,]*(?:\.\d+)?)\s*(?:per month|monthly|a month|/month)",
        r"(\d[\d,]*(?:\.\d+)?)\s*(?:per month|monthly|a month|/month).*(?:earn|income|salary)",
    ],
    "monthly_debts": [
        r"(?:debt|loan|installment|repayment|obligation)[^\d]*(?:RM\s?)?(\d[\d,]*(?:\.\d+)?)",
        r"(?:owe|paying)[^\d]*(?:RM\s?)?(\d[\d,]*(?:\.\d+)?)\s*(?:per month|monthly|a month)?",
        r"(?:RM|rm)\s?(\d[\d,]*(?:\.\d+)?)\s*.*(?:debt|loan|installment|obligation)",
    ],
    "loan_amount": [
        r"(?:loan|borrow|need|requesting)[^\d]*(?:RM\s?)?(\d[\d,]*(?:\.\d+)?)",
        r"(?:RM|rm)\s?(\d[\d,]*(?:\.\d+)?)\s*(?:loan|home loan|personal loan)",
    ],
    "loan_term_months": [
        r"(\d+)\s*(?:months?|month loan)",
        r"(\d+)\s*year[s]?\s*(?:loan|term)",
    ],
    "property_value": [
        r"(?:property|house|home)[^\d]*(?:worth|value|valued at|costs?)[^\d]*(?:RM\s?)?(\d[\d,]*(?:\.\d+)?)",
        r"(?:RM|rm)\s?(\d[\d,]*(?:\.\d+)?)\s*(?:property|house|home)",
    ],
}

_EMPLOYMENT_KEYWORDS = {
    "employed": ["employed", "working", "salaried", "full.time", "permanent"],
    "self-employed": ["self.employed", "freelance", "own business", "entrepreneur"],
    "unemployed": ["unemployed", "not working", "jobless"],
    "retired": ["retired", "pensioner"],
}

_LOAN_TYPE_KEYWORDS = {
    "home": ["home loan", "house loan", "mortgage", "property loan"],
    "personal": ["personal loan", "personal financing"],
    "auto": ["car loan", "vehicle loan", "auto loan"],
    "business": ["business loan"],
}


def _parse_number(s: str) -> float:
    return float(s.replace(",", ""))


_MAX_INPUT_LEN = 2000  # guard against ReDoS on very long inputs


def _extract_fields(text: str, current: Dict[str, Any]) -> Dict[str, Any]:
    """Extract structured fields from free-text using heuristics."""
    fields = dict(current)
    # Truncate to prevent polynomial ReDoS on adversarial inputs
    lower = text[:_MAX_INPUT_LEN].lower()

    # Employment status
    if fields.get("employment_status") is None:
        for status, keywords in _EMPLOYMENT_KEYWORDS.items():
            if any(re.search(kw, lower) for kw in keywords):
                fields["employment_status"] = status
                break

    # Loan type
    if fields.get("loan_type") is None:
        for ltype, keywords in _LOAN_TYPE_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                fields["loan_type"] = ltype
                break

    # Loan term: convert years to months if needed
    if fields.get("loan_term_months") is None:
        m = re.search(r"(\d{1,3})\s+year[s]?\b", lower)
        if m:
            fields["loan_term_months"] = int(m.group(1)) * 12
        else:
            m = re.search(r"(\d{1,4})\s+months?\b", lower)
            if m:
                fields["loan_term_months"] = int(m.group(1))

    # Numeric fields via patterns
    numeric_map = {
        "monthly_income": _FIELD_PATTERNS["monthly_income"],
        "monthly_debts": _FIELD_PATTERNS["monthly_debts"],
        "loan_amount": _FIELD_PATTERNS["loan_amount"],
        "property_value": _FIELD_PATTERNS["property_value"],
    }
    for field, patterns in numeric_map.items():
        if fields.get(field) is None:
            for pat in patterns:
                m = re.search(pat, lower)
                if m:
                    try:
                        fields[field] = _parse_number(m.group(1))
                        break
                    except ValueError:
                        pass

    # Name
    if fields.get("applicant_name") is None:
        for pat in _FIELD_PATTERNS["applicant_name"]:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                fields["applicant_name"] = m.group(1).strip()
                break

    return fields


class MockAgentClient(AgentClient):
    """Deterministic mock implementation – no external LLM calls required."""

    async def intake(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        extracted_fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        updated = _extract_fields(user_message, extracted_fields)

        required = [
            ("applicant_name", "your full name"),
            ("monthly_income", "your gross monthly income (RM)"),
            ("monthly_debts", "your existing monthly debt obligations (RM, enter 0 if none)"),
            ("employment_status", "your employment status (employed / self-employed / unemployed)"),
            ("loan_type", "the type of loan you need (home / personal / auto / business)"),
            ("loan_amount", "the loan amount you are requesting (RM)"),
            ("loan_term_months", "your preferred repayment period (in months or years)"),
        ]
        missing = [label for attr, label in required if updated.get(attr) is None]

        if missing:
            question = "To continue processing your application, I need a few more details:\n"
            for item in missing[:3]:  # ask max 3 at a time
                question += f"  • {item}\n"
            assistant_message = question.strip()
        else:
            assistant_message = (
                f"Thank you, {updated.get('applicant_name', 'applicant')}! "
                "I have captured all the required information. "
                "I am now forwarding your application for analysis and verification."
            )

        return {
            "extracted_fields": updated,
            "assistant_message": assistant_message,
            "missing_fields": missing,
        }

    async def underwriter(
        self,
        extracted_fields: Dict[str, Any],
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        dsr = analysis.get("dsr")
        risk = analysis.get("risk_level", "unknown")
        installment = analysis.get("estimated_monthly_installment")

        summary_parts = []
        flags = []

        if dsr is not None:
            summary_parts.append(f"DSR calculated at {dsr:.1f}% ({risk} risk).")
            if dsr >= 60:
                flags.append("DSR exceeds 60% threshold – high risk.")
            elif dsr >= 40:
                flags.append("DSR between 40–60% – medium risk; additional scrutiny advised.")

        if installment is not None:
            summary_parts.append(f"Estimated monthly installment: RM {installment:,.2f}.")

        if extracted_fields.get("employment_status") == "self-employed":
            flags.append("Self-employed applicant – income verification may be required.")

        if not summary_parts:
            summary_parts.append("Insufficient data for full underwriting analysis.")

        return {
            "assessment_summary": " ".join(summary_parts),
            "risk_flags": flags,
        }

    async def verification(
        self,
        extracted_fields: Dict[str, Any],
        tool_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        parts = []
        flags = []

        credit_score = tool_results.get("credit_score")
        credit_band = tool_results.get("credit_band")
        credit_failed = tool_results.get("credit_check_failed", False)

        if credit_failed:
            flags.append("Credit bureau check failed – manual verification required.")
            parts.append("Credit check: FAILED (bureau unavailable).")
        elif credit_score:
            parts.append(f"Credit score: {credit_score} ({credit_band}).")
            if credit_score < 650:
                flags.append(f"Credit score {credit_score} is below preferred threshold of 650.")

        valuation = tool_results.get("property_valuation")
        val_failed = tool_results.get("valuation_check_failed", False)

        if val_failed:
            flags.append("Property valuation service unavailable – manual appraisal needed.")
            parts.append("Property valuation: FAILED (service unavailable).")
        elif valuation:
            loan_amount = extracted_fields.get("loan_amount")
            if loan_amount and valuation > 0:
                ltv = (loan_amount / valuation) * 100
                parts.append(f"Property valued at RM {valuation:,.2f} (LTV: {ltv:.1f}%).")
                if ltv > 90:
                    flags.append(f"High LTV ratio of {ltv:.1f}% – additional collateral may be required.")

        return {
            "verification_summary": " ".join(parts) if parts else "No external checks performed.",
            "flags": flags,
        }

    async def comms(
        self,
        decision: Dict[str, Any],
        applicant_name: Optional[str],
    ) -> str:
        name = applicant_name or "Applicant"
        status = decision.get("loan_status", "incomplete")
        dsr = decision.get("dsr", "N/A")
        next_action = decision.get("next_action", "")
        missing = decision.get("missing_information", [])
        risk = decision.get("risk_level", "unknown")

        if status == "approved":
            return (
                f"Dear {name},\n\n"
                f"We are pleased to inform you that your loan application has been **approved**.\n\n"
                f"Your Debt-Service Ratio (DSR) of {dsr} is within our acceptable range, "
                f"and your credit profile meets our lending criteria.\n\n"
                f"**Next step:** {next_action}\n\n"
                f"Congratulations, and thank you for choosing us!"
            )
        elif status == "rejected":
            return (
                f"Dear {name},\n\n"
                f"After a thorough review of your application, we regret to inform you that "
                f"your loan application has been **declined** at this time.\n\n"
                f"Your current Debt-Service Ratio (DSR) of {dsr} exceeds our maximum threshold of 60%.\n\n"
                f"**Next step:** {next_action}\n\n"
                f"You are welcome to reapply once your financial position has improved."
            )
        elif status == "manual_review":
            return (
                f"Dear {name},\n\n"
                f"Your loan application is currently under **manual review** by our underwriting team.\n\n"
                f"DSR: {dsr} | Risk level: {risk.upper()}\n\n"
                f"**Next step:** {next_action}\n\n"
                f"Our team will contact you within 3–5 business days."
            )
        else:
            missing_str = "\n".join(f"  • {m}" for m in missing) if missing else "  (none)"
            return (
                f"Dear {name},\n\n"
                f"Thank you for starting your loan application. "
                f"To proceed, we still require the following information:\n\n"
                f"{missing_str}\n\n"
                f"**Next step:** {next_action}\n\n"
                f"Please reply with the above details and we will continue processing your application."
            )
