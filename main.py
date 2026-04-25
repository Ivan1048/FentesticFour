"""
AI Loan Processing Agent — FastAPI Backend
Multi-agent loan orchestration system for UMHackathon 2026
"""

import os
import uuid
import base64
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv, set_key

from models import UserAuth, LoanInput, ApiKeyConfig
from agents import OrchestratorAgent

# ─── Load .env on startup ──────────────────
ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(ENV_PATH)

# ─── App ────────────────────────────────────
app = FastAPI(
    title="AI Loan Processing Agent",
    description="Multi-agent loan orchestration system — UMHackathon 2026",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── State ──────────────────────────────────
db: Dict[str, dict] = {}
gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")
orchestrator: OrchestratorAgent = OrchestratorAgent(api_key=gemini_api_key) if gemini_api_key else OrchestratorAgent()

# ─── Uploads directory ──────────────────────
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_MIME = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "application/pdf",
    "text/plain",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# ─── Static files ───────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


# ─── Authentication ─────────────────────────
@app.post("/auth/register", tags=["Authentication"])
async def register(data: UserAuth):
    if data.username in db:
        raise HTTPException(status_code=400, detail="Username already exists. Please login instead.")

    db[data.username] = {
        "password": data.password,
        "authenticated": False,
        "partial_data": {},
        "history": [],
    }
    return {"status": "success", "message": "Registration successful! Please login to continue."}


@app.post("/auth/login", tags=["Authentication"])
async def login(data: UserAuth):
    if data.username not in db:
        raise HTTPException(status_code=404, detail="User not found. Please register first.")

    if db[data.username]["password"] != data.password:
        raise HTTPException(status_code=401, detail="Invalid password.")

    db[data.username]["authenticated"] = True
    return {"status": "success", "message": f"Welcome back, {data.username}!"}


# ─── Configuration ──────────────────────────
@app.post("/config/api-key", tags=["Configuration"])
async def set_api_key(config: ApiKeyConfig):
    global gemini_api_key, orchestrator
    gemini_api_key = config.api_key
    orchestrator = OrchestratorAgent(api_key=gemini_api_key)

    # Persist to .env file so it survives server restarts
    if not ENV_PATH.exists():
        ENV_PATH.write_text("# LoanAI Configuration\n")
    set_key(str(ENV_PATH), "GEMINI_API_KEY", gemini_api_key)

    return {"status": "success", "message": "Gemini API key saved and persisted."}


@app.get("/config/status", tags=["Configuration"])
async def config_status():
    return {"gemini_configured": bool(gemini_api_key)}


# ─── Loan Processing ───────────────────────
@app.post("/loan/process", tags=["Loan Processing"])
async def process_loan(data: LoanInput):
    user = db.get(data.username)
    if not user or not user.get("authenticated"):
        raise HTTPException(status_code=403, detail="Not authenticated. Please login first.")

    existing = user.get("partial_data", {})
    result = await orchestrator.process(data.text, existing if existing else None)

    # Persist partial data for multi-turn clarification
    user["partial_data"] = result.get("extracted_data", {})
    user["history"].append({"input": data.text, "result": result})

    # Reset partial data once a final decision is reached
    if result.get("loan_status") not in ("Incomplete", ""):
        user["partial_data"] = {}

    return result


# ─── File Upload + Processing ───────────────
@app.post("/loan/upload", tags=["Loan Processing"])
async def process_upload(
    file: UploadFile = File(...),
    username: str = Form(...),
    text: str = Form(""),
):
    """Process a loan application with an uploaded document (payslip, bank statement, IC)."""

    # Auth check
    user = db.get(username)
    if not user or not user.get("authenticated"):
        raise HTTPException(status_code=403, detail="Not authenticated. Please login first.")

    # Validate file type
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Please upload an image (JPG/PNG) or PDF.",
        )

    # Read file bytes
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10 MB.")

    # Save copy for audit
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin"
    saved_name = f"{uuid.uuid4().hex[:12]}.{ext}"
    (UPLOAD_DIR / saved_name).write_bytes(file_bytes)

    # Encode to base64 for Gemini
    file_b64 = base64.b64encode(file_bytes).decode("utf-8")

    # Combine text + file for extraction
    user_text = text.strip() if text else "Please extract loan application data from this document."

    existing = user.get("partial_data", {})
    result = await orchestrator.process(
        text=user_text,
        existing_data=existing if existing else None,
        file_data=file_b64,
        file_mime=file.content_type,
        file_name=file.filename,
    )

    # Persist partial data for multi-turn clarification
    user["partial_data"] = result.get("extracted_data", {})
    user["history"].append({
        "input": user_text,
        "file": file.filename,
        "result": result,
    })

    # Reset partial data once a final decision is reached
    if result.get("loan_status") not in ("Incomplete", ""):
        user["partial_data"] = {}

    return result


@app.post("/loan/reset", tags=["Loan Processing"])
async def reset_loan(data: dict):
    username = data.get("username")
    user = db.get(username)
    if user:
        user["partial_data"] = {}
    return {"status": "success", "message": "Loan application reset."}


# ─── Entry point ────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
