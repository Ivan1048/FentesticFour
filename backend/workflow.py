"""Workflow state machine: INTAKE -> VALIDATE -> ANALYZE -> EXTERNAL_CHECKS -> DECISION -> DONE."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .agent.base import AgentClient
from .schemas import (
    AnalysisResult,
    ExtractedFields,
    RiskLevel,
    ToolResults,
    WorkflowStep,
)
from .tools.credit import check_credit_score
from .tools.dsr import (
    assess_affordability,
    calculate_dsr,
    calculate_monthly_installment,
)
from .tools.policy import identify_missing_fields, make_decision
from .tools.valuation import get_property_valuation

logger = logging.getLogger(__name__)


async def run_workflow_step(
    current_step: WorkflowStep,
    user_message: str,
    conversation_history: list,
    extracted_fields: ExtractedFields,
    analysis: AnalysisResult,
    tool_results: ToolResults,
    agent: AgentClient,
    simulate_credit_failure: bool = False,
    simulate_valuation_failure: bool = False,
) -> Dict[str, Any]:
    """
    Execute the current workflow step and return updated state.

    Returns:
        {
            "next_step": WorkflowStep,
            "extracted_fields": ExtractedFields,
            "analysis": AnalysisResult,
            "tool_results": ToolResults,
            "assistant_message": str,
            "agent_events": [{"agent_role": str, "input_summary": str, "output_summary": str}],
            "decision": DecisionOutput,
        }
    """
    agent_events = []
    fields_dict = extracted_fields.model_dump()
    analysis_dict = analysis.model_dump()
    tool_dict = tool_results.model_dump()

    # ------------------------------------------------------------------ INTAKE
    if current_step == WorkflowStep.INTAKE:
        result = await agent.intake(user_message, conversation_history, fields_dict)
        updated_fields = ExtractedFields(**{
            k: result["extracted_fields"].get(k) or fields_dict.get(k)
            for k in fields_dict
        })
        agent_events.append({
            "agent_role": "Intake Agent",
            "input_summary": f"User message: '{user_message[:80]}…'" if len(user_message) > 80 else f"User message: '{user_message}'",
            "output_summary": result.get("assistant_message", "")[:120],
        })
        missing = identify_missing_fields(updated_fields)
        next_step = WorkflowStep.VALIDATE if not missing else WorkflowStep.INTAKE
        decision = make_decision(updated_fields, analysis, tool_results)
        return {
            "next_step": next_step,
            "extracted_fields": updated_fields,
            "analysis": analysis,
            "tool_results": tool_results,
            "assistant_message": result.get("assistant_message", ""),
            "agent_events": agent_events,
            "decision": decision,
        }

    # ---------------------------------------------------------------- VALIDATE
    if current_step == WorkflowStep.VALIDATE:
        missing = identify_missing_fields(extracted_fields)
        if missing:
            # Loop back to intake to gather missing info
            result = await agent.intake(user_message, conversation_history, fields_dict)
            updated_fields = ExtractedFields(**{
                k: result["extracted_fields"].get(k) or fields_dict.get(k)
                for k in fields_dict
            })
            agent_events.append({
                "agent_role": "Intake Agent (re-prompt)",
                "input_summary": f"Missing fields: {', '.join(missing[:3])}",
                "output_summary": result.get("assistant_message", "")[:120],
            })
            missing2 = identify_missing_fields(updated_fields)
            next_step = WorkflowStep.ANALYZE if not missing2 else WorkflowStep.INTAKE
            decision = make_decision(updated_fields, analysis, tool_results)
            return {
                "next_step": next_step,
                "extracted_fields": updated_fields,
                "analysis": analysis,
                "tool_results": tool_results,
                "assistant_message": result.get("assistant_message", ""),
                "agent_events": agent_events,
                "decision": decision,
            }
        next_step = WorkflowStep.ANALYZE
        decision = make_decision(extracted_fields, analysis, tool_results)
        return {
            "next_step": next_step,
            "extracted_fields": extracted_fields,
            "analysis": analysis,
            "tool_results": tool_results,
            "assistant_message": "All required fields validated. Proceeding to financial analysis.",
            "agent_events": agent_events,
            "decision": decision,
        }

    # ----------------------------------------------------------------- ANALYZE
    if current_step == WorkflowStep.ANALYZE:
        income = extracted_fields.monthly_income or 0
        debts = extracted_fields.monthly_debts or 0
        loan_amount = extracted_fields.loan_amount or 0
        term = extracted_fields.loan_term_months or 360

        installment = calculate_monthly_installment(loan_amount, term) if loan_amount else 0
        dsr = calculate_dsr(income, debts, installment)
        affordability = assess_affordability(dsr)

        updated_analysis = AnalysisResult(
            dsr=round(dsr, 2),
            estimated_monthly_installment=round(installment, 2),
            affordability_ratio=round(installment / income, 4) if income else None,
            risk_level=RiskLevel(affordability["risk_level"]),
        )
        analysis_dict_upd = updated_analysis.model_dump()
        uw_result = await agent.underwriter(fields_dict, analysis_dict_upd)
        agent_events.append({
            "agent_role": "Underwriter Agent",
            "input_summary": f"DSR={dsr:.1f}%, installment=RM{installment:,.2f}",
            "output_summary": uw_result.get("assessment_summary", "")[:120],
        })
        decision = make_decision(extracted_fields, updated_analysis, tool_results)
        return {
            "next_step": WorkflowStep.EXTERNAL_CHECKS,
            "extracted_fields": extracted_fields,
            "analysis": updated_analysis,
            "tool_results": tool_results,
            "assistant_message": uw_result.get("assessment_summary", "Analysis complete."),
            "agent_events": agent_events,
            "decision": decision,
        }

    # --------------------------------------------------------- EXTERNAL_CHECKS
    if current_step == WorkflowStep.EXTERNAL_CHECKS:
        # Credit check
        credit_result = check_credit_score(
            extracted_fields.applicant_name or "unknown",
            simulate_failure=simulate_credit_failure,
        )
        # Property valuation (only for home loans)
        val_result = get_property_valuation(
            extracted_fields.property_address,
            extracted_fields.property_value,
            simulate_failure=simulate_valuation_failure,
        )
        updated_tool = ToolResults(
            credit_score=credit_result.get("score"),
            credit_band=credit_result.get("band"),
            credit_check_failed=credit_result.get("failed", False),
            property_valuation=val_result.get("valuation"),
            valuation_check_failed=val_result.get("failed", False),
        )
        tool_dict_upd = updated_tool.model_dump()
        ver_result = await agent.verification(fields_dict, tool_dict_upd)
        agent_events.append({
            "agent_role": "Verification Agent",
            "input_summary": f"Credit: {credit_result.get('message', '')[:60]}",
            "output_summary": ver_result.get("verification_summary", "")[:120],
        })
        decision = make_decision(extracted_fields, analysis, updated_tool)
        return {
            "next_step": WorkflowStep.DECISION,
            "extracted_fields": extracted_fields,
            "analysis": analysis,
            "tool_results": updated_tool,
            "assistant_message": ver_result.get("verification_summary", "External checks complete."),
            "agent_events": agent_events,
            "decision": decision,
        }

    # ---------------------------------------------------------------- DECISION
    if current_step == WorkflowStep.DECISION:
        decision = make_decision(extracted_fields, analysis, tool_results)
        comms_msg = await agent.comms(decision.model_dump(), extracted_fields.applicant_name)
        agent_events.append({
            "agent_role": "Comms Agent",
            "input_summary": f"Status: {decision.loan_status}, DSR: {decision.dsr}",
            "output_summary": comms_msg[:120],
        })
        return {
            "next_step": WorkflowStep.DONE,
            "extracted_fields": extracted_fields,
            "analysis": analysis,
            "tool_results": tool_results,
            "assistant_message": comms_msg,
            "agent_events": agent_events,
            "decision": decision,
        }

    # -------------------------------------------------------------------- DONE
    # Re-running after done: just reply politely
    decision = make_decision(extracted_fields, analysis, tool_results)
    return {
        "next_step": WorkflowStep.DONE,
        "extracted_fields": extracted_fields,
        "analysis": analysis,
        "tool_results": tool_results,
        "assistant_message": "Your application has been fully processed. Please refer to the decision panel for the outcome.",
        "agent_events": agent_events,
        "decision": decision,
    }
