"""Data models for the AI Loan Processing Agent."""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class UserAuth(BaseModel):
    """Authentication request model."""
    username: str
    password: str


class LoanInput(BaseModel):
    """Loan processing input from chat."""
    username: str
    text: str


class ApiKeyConfig(BaseModel):
    """Gemini API key configuration."""
    api_key: str


class LoanData(BaseModel):
    """Structured loan application data."""
    loan_type: Optional[str] = None
    income: Optional[float] = None
    employment_status: Optional[str] = None
    employment_duration: Optional[float] = None
    property_price: Optional[float] = None
    existing_debt: Optional[float] = None
    country: Optional[str] = "Malaysia"


class AgentLog(BaseModel):
    """Log entry from an individual agent."""
    agent_name: str
    status: str  # "success", "warning", "error", "skipped"
    message: str
    data: Dict[str, Any] = {}
    duration_ms: int = 0


class PipelineResult(BaseModel):
    """Final structured output from the loan processing pipeline."""
    intent: str = "Loan Application"
    extracted_data: Dict[str, Any] = {}
    missing_fields: List[str] = []
    dsr: str = ""
    risk_level: str = ""
    loan_status: str = ""
    credit_score: str = ""
    valuation_result: str = ""
    legal_status: str = ""
    contract_safe_check: str = ""
    next_action: str = ""
    user_message: str = ""
    agent_trace: List[Dict[str, Any]] = []
