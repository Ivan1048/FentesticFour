"""Abstract AgentClient interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AgentClient(ABC):
    """Provider-agnostic interface for LLM/agent calls."""

    @abstractmethod
    async def intake(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        extracted_fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Intake agent: extract structured fields from user message.

        Returns:
            {
                "extracted_fields": {...},
                "assistant_message": str,
                "missing_fields": [str, ...],
            }
        """
        ...

    @abstractmethod
    async def underwriter(
        self,
        extracted_fields: Dict[str, Any],
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Underwriter agent: analyse risk and financial metrics.

        Returns:
            {
                "assessment_summary": str,
                "risk_flags": [str, ...],
            }
        """
        ...

    @abstractmethod
    async def verification(
        self,
        extracted_fields: Dict[str, Any],
        tool_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Verification agent: interpret external tool results.

        Returns:
            {
                "verification_summary": str,
                "flags": [str, ...],
            }
        """
        ...

    @abstractmethod
    async def comms(
        self,
        decision: Dict[str, Any],
        applicant_name: Optional[str],
    ) -> str:
        """
        Communications agent: generate professional reply for applicant.

        Returns a natural-language message string.
        """
        ...
