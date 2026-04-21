"""FastAPI main application – Loan Processing Demo."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import storage
from .agent.mock import MockAgentClient
from .schemas import (
    AgentEvent,
    AnalysisResult,
    ApplicationCreate,
    ApplicationOut,
    DecisionOutput,
    ExtractedFields,
    MessageCreate,
    MessageOut,
    MessageRole,
    SendMessageResponse,
    ToolResults,
    WorkflowStep,
)
from .workflow import run_workflow_step

# ------------------------------------------------------------------- Bootstrap

AGENT_PROVIDER = os.getenv("AGENT_PROVIDER", "mock")


def _build_agent():
    if AGENT_PROVIDER == "zai":
        from .agent.zai import ZaiAgentClient
        return ZaiAgentClient()
    return MockAgentClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await storage.init_db()
    yield
    await storage.close_pool()


app = FastAPI(title="FentesticFour Loan Demo", version="1.0.0", lifespan=lifespan)

# --------------------------------------------------------------------- Statics

_BASE = os.path.dirname(__file__)
_FRONTEND = os.path.join(_BASE, "..", "frontend")

app.mount("/static", StaticFiles(directory=os.path.join(_FRONTEND, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(_FRONTEND, "templates"))

# ------------------------------------------------------------------ HTML pages


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/app/{app_id}", response_class=HTMLResponse)
async def app_console(request: Request, app_id: str):
    row = await storage.get_application(app_id)
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    return templates.TemplateResponse("app.html", {"request": request, "app_id": app_id})


# ----------------------------------------------------------------- API helpers

def _build_app_out(row: dict, messages: list, events: list) -> ApplicationOut:
    extracted = ExtractedFields(**json.loads(row["extracted_fields"]) if isinstance(row["extracted_fields"], str) else row["extracted_fields"])
    analysis = AnalysisResult(**json.loads(row["analysis"]) if isinstance(row["analysis"], str) else row["analysis"])
    tool_results = ToolResults(**json.loads(row["tool_results"]) if isinstance(row["tool_results"], str) else row["tool_results"])
    raw_decision = json.loads(row["decision"]) if isinstance(row["decision"], str) else row["decision"]
    decision = DecisionOutput(**raw_decision) if raw_decision else DecisionOutput()

    msgs_out = [
        MessageOut(
            id=m["id"],
            application_id=m["application_id"],
            role=MessageRole(m["role"]),
            content=m["content"],
            created_at=m["created_at"],
        )
        for m in messages
    ]
    evts_out = [
        AgentEvent(
            id=e["id"],
            application_id=e["application_id"],
            agent_role=e["agent_role"],
            input_summary=e["input_summary"],
            output_summary=e["output_summary"],
            created_at=e["created_at"],
        )
        for e in events
    ]
    return ApplicationOut(
        id=row["id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        current_step=WorkflowStep(row["current_step"]),
        extracted_fields=extracted,
        analysis=analysis,
        tool_results=tool_results,
        decision=decision,
        messages=msgs_out,
        agent_events=evts_out,
    )


# ----------------------------------------------------------------- API routes

@app.post("/api/applications", response_model=ApplicationOut)
async def create_application(body: ApplicationCreate):
    row = await storage.create_application(body.applicant_name)
    return _build_app_out(row, [], [])


@app.get("/api/applications/{app_id}", response_model=ApplicationOut)
async def get_application(app_id: str):
    row = await storage.get_application(app_id)
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    messages = await storage.get_messages(app_id)
    events = await storage.get_agent_events(app_id)
    return _build_app_out(row, messages, events)


@app.post("/api/applications/{app_id}/messages", response_model=SendMessageResponse)
async def send_message(
    app_id: str,
    body: MessageCreate,
    simulate_credit_failure: bool = Query(False),
    simulate_valuation_failure: bool = Query(False),
):
    row = await storage.get_application(app_id)
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")

    # Persist user message
    await storage.add_message(app_id, "user", body.content)

    # Reconstruct state
    extracted = ExtractedFields(**json.loads(row["extracted_fields"]) if isinstance(row["extracted_fields"], str) else row["extracted_fields"])
    analysis = AnalysisResult(**json.loads(row["analysis"]) if isinstance(row["analysis"], str) else row["analysis"])
    tool_results = ToolResults(**json.loads(row["tool_results"]) if isinstance(row["tool_results"], str) else row["tool_results"])
    current_step = WorkflowStep(row["current_step"])

    # Build conversation history for agent context
    messages = await storage.get_messages(app_id)
    history = [{"role": m["role"], "content": m["content"]} for m in messages]

    agent = _build_agent()

    result = await run_workflow_step(
        current_step=current_step,
        user_message=body.content,
        conversation_history=history,
        extracted_fields=extracted,
        analysis=analysis,
        tool_results=tool_results,
        agent=agent,
        simulate_credit_failure=simulate_credit_failure,
        simulate_valuation_failure=simulate_valuation_failure,
    )

    # If step was ANALYZE or EXTERNAL_CHECKS – auto-advance without user interaction
    next_step = result["next_step"]
    if current_step == WorkflowStep.VALIDATE and next_step == WorkflowStep.ANALYZE:
        # Run ANALYZE immediately
        result2 = await run_workflow_step(
            current_step=WorkflowStep.ANALYZE,
            user_message="",
            conversation_history=history,
            extracted_fields=result["extracted_fields"],
            analysis=result["analysis"],
            tool_results=result["tool_results"],
            agent=agent,
            simulate_credit_failure=simulate_credit_failure,
            simulate_valuation_failure=simulate_valuation_failure,
        )
        result["agent_events"].extend(result2["agent_events"])
        result["analysis"] = result2["analysis"]
        result["next_step"] = result2["next_step"]
        # Keep assistant message from intake

        # Run EXTERNAL_CHECKS immediately
        result3 = await run_workflow_step(
            current_step=WorkflowStep.EXTERNAL_CHECKS,
            user_message="",
            conversation_history=history,
            extracted_fields=result2["extracted_fields"],
            analysis=result2["analysis"],
            tool_results=result2["tool_results"],
            agent=agent,
            simulate_credit_failure=simulate_credit_failure,
            simulate_valuation_failure=simulate_valuation_failure,
        )
        result["agent_events"].extend(result3["agent_events"])
        result["tool_results"] = result3["tool_results"]
        result["next_step"] = result3["next_step"]

        # Run DECISION immediately
        result4 = await run_workflow_step(
            current_step=WorkflowStep.DECISION,
            user_message="",
            conversation_history=history,
            extracted_fields=result3["extracted_fields"],
            analysis=result3["analysis"],
            tool_results=result3["tool_results"],
            agent=agent,
        )
        result["agent_events"].extend(result4["agent_events"])
        result["decision"] = result4["decision"]
        result["next_step"] = result4["next_step"]
        result["assistant_message"] = result4["assistant_message"]

    elif current_step == WorkflowStep.ANALYZE:
        # Run EXTERNAL_CHECKS immediately
        result3 = await run_workflow_step(
            current_step=WorkflowStep.EXTERNAL_CHECKS,
            user_message="",
            conversation_history=history,
            extracted_fields=result["extracted_fields"],
            analysis=result["analysis"],
            tool_results=result["tool_results"],
            agent=agent,
            simulate_credit_failure=simulate_credit_failure,
            simulate_valuation_failure=simulate_valuation_failure,
        )
        result["agent_events"].extend(result3["agent_events"])
        result["tool_results"] = result3["tool_results"]
        result["next_step"] = result3["next_step"]

        # Run DECISION immediately
        result4 = await run_workflow_step(
            current_step=WorkflowStep.DECISION,
            user_message="",
            conversation_history=history,
            extracted_fields=result3["extracted_fields"],
            analysis=result3["analysis"],
            tool_results=result3["tool_results"],
            agent=agent,
        )
        result["agent_events"].extend(result4["agent_events"])
        result["decision"] = result4["decision"]
        result["next_step"] = result4["next_step"]
        result["assistant_message"] = result4["assistant_message"]

    # Persist assistant message
    assistant_row = await storage.add_message(app_id, "assistant", result["assistant_message"])

    # Persist agent events
    for evt in result["agent_events"]:
        await storage.add_agent_event(
            app_id,
            evt["agent_role"],
            evt["input_summary"],
            evt["output_summary"],
        )

    # Update application state
    await storage.update_application(
        app_id,
        result["next_step"].value,
        result["extracted_fields"].model_dump(),
        result["analysis"].model_dump(),
        result["tool_results"].model_dump(),
        result["decision"].model_dump(),
    )

    # Build response
    all_messages = await storage.get_messages(app_id)
    all_events = await storage.get_agent_events(app_id)
    updated_row = await storage.get_application(app_id)
    app_out = _build_app_out(updated_row, all_messages, all_events)

    asst_msg_out = MessageOut(
        id=assistant_row["id"],
        application_id=assistant_row["application_id"],
        role=MessageRole.ASSISTANT,
        content=assistant_row["content"],
        created_at=assistant_row["created_at"],
    )

    return SendMessageResponse(
        assistant_message=asst_msg_out,
        application=app_out,
        decision=result["decision"],
    )
