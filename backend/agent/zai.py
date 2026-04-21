"""Z.Ai AgentClient stub – swap in tomorrow with real endpoint/key."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

from .base import AgentClient


ZAI_API_BASE = os.getenv("ZAI_API_BASE", "https://api.z.ai/v1")
ZAI_API_KEY = os.getenv("ZAI_API_KEY", "")
ZAI_MODEL = os.getenv("ZAI_MODEL", "zai-default")


class ZaiAgentClient(AgentClient):
    """
    Z.Ai provider implementation.

    Requires environment variables:
      ZAI_API_BASE  – base URL (default: https://api.z.ai/v1)
      ZAI_API_KEY   – your Z.Ai API key
      ZAI_MODEL     – model name (default: zai-default)

    This stub mirrors the OpenAI-compatible chat completion API.
    Replace the _call method body with Z.Ai-specific SDK/endpoint as needed.
    """

    async def _call(self, system_prompt: str, user_content: str) -> str:
        """Send a chat completion request to Z.Ai and return the assistant message."""
        headers = {
            "Authorization": f"Bearer {ZAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": ZAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{ZAI_API_BASE}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def intake(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        extracted_fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        import json

        system = (
            "You are an expert intake officer for a financial institution. "
            "Your job is to extract structured loan application fields from the user's message. "
            "Return ONLY valid JSON with keys: extracted_fields (dict), assistant_message (str), missing_fields (list of str). "
            "Fields to extract: applicant_name, monthly_income (float), monthly_debts (float), "
            "employment_status, loan_type, loan_amount (float), loan_term_months (int), "
            "property_value (float or null), property_address (str or null). "
            "Do not invent values; only extract what is explicitly stated."
        )
        user_content = (
            f"Current extracted fields: {json.dumps(extracted_fields)}\n"
            f"New user message: {user_message}"
        )
        raw = await self._call(system, user_content)
        return json.loads(raw)

    async def underwriter(
        self,
        extracted_fields: Dict[str, Any],
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        import json

        system = (
            "You are a senior underwriter at a financial institution. "
            "Analyse the loan application data and financial metrics provided. "
            "Return ONLY valid JSON with keys: assessment_summary (str), risk_flags (list of str)."
        )
        user_content = (
            f"Application fields: {json.dumps(extracted_fields)}\n"
            f"Analysis metrics: {json.dumps(analysis)}"
        )
        raw = await self._call(system, user_content)
        return json.loads(raw)

    async def verification(
        self,
        extracted_fields: Dict[str, Any],
        tool_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        import json

        system = (
            "You are a verification officer at a financial institution. "
            "Interpret the external tool results (credit check, property valuation) in context of the application. "
            "Return ONLY valid JSON with keys: verification_summary (str), flags (list of str)."
        )
        user_content = (
            f"Application fields: {json.dumps(extracted_fields)}\n"
            f"External tool results: {json.dumps(tool_results)}"
        )
        raw = await self._call(system, user_content)
        return json.loads(raw)

    async def comms(
        self,
        decision: Dict[str, Any],
        applicant_name: Optional[str],
    ) -> str:
        import json

        system = (
            "You are a professional customer communications officer at a financial institution. "
            "Write a clear, empathetic, and professional message to the loan applicant based on the decision provided. "
            "Use markdown formatting. Address the applicant by name."
        )
        user_content = (
            f"Applicant name: {applicant_name or 'Applicant'}\n"
            f"Decision: {json.dumps(decision)}"
        )
        return await self._call(system, user_content)
