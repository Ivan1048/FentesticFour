from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WorkflowStep(str, Enum):
    INTAKE = "INTAKE"
    VALIDATE = "VALIDATE"
    ANALYZE = "ANALYZE"
    EXTERNAL_CHECKS = "EXTERNAL_CHECKS"
    DECISION = "DECISION"
    DONE = "DONE"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class LoanStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"
    INCOMPLETE = "incomplete"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ExtractedFields(BaseModel):
    applicant_name: Optional[str] = None
    monthly_income: Optional[float] = None
    monthly_debts: Optional[float] = None
    employment_status: Optional[str] = None
    loan_type: Optional[str] = None
    loan_amount: Optional[float] = None
    loan_term_months: Optional[int] = None
    property_value: Optional[float] = None
    property_address: Optional[str] = None
    credit_score_provided: Optional[int] = None


class ToolResults(BaseModel):
    credit_score: Optional[int] = None
    credit_band: Optional[str] = None
    credit_check_failed: bool = False
    property_valuation: Optional[float] = None
    valuation_check_failed: bool = False


class AnalysisResult(BaseModel):
    dsr: Optional[float] = None
    estimated_monthly_installment: Optional[float] = None
    affordability_ratio: Optional[float] = None
    risk_level: RiskLevel = RiskLevel.UNKNOWN


class DecisionOutput(BaseModel):
    loan_status: LoanStatus = LoanStatus.INCOMPLETE
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    dsr: Optional[str] = None
    missing_information: List[str] = Field(default_factory=list)
    next_action: str = "Provide required information"


class AgentEvent(BaseModel):
    id: Optional[int] = None
    application_id: str
    agent_role: str
    input_summary: str
    output_summary: str
    created_at: Optional[datetime] = None


class MessageCreate(BaseModel):
    content: str


class MessageOut(BaseModel):
    id: int
    application_id: str
    role: MessageRole
    content: str
    created_at: datetime


class ApplicationCreate(BaseModel):
    applicant_name: Optional[str] = None


class ApplicationOut(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    current_step: WorkflowStep
    extracted_fields: ExtractedFields
    analysis: AnalysisResult
    tool_results: ToolResults
    decision: DecisionOutput
    messages: List[MessageOut] = Field(default_factory=list)
    agent_events: List[AgentEvent] = Field(default_factory=list)


class SendMessageResponse(BaseModel):
    assistant_message: MessageOut
    application: ApplicationOut
    decision: DecisionOutput
