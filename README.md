# 🤖 LoanAI — Intelligent Multi-Agent Loan Processing System

> **UMHackathon 2026 · Domain 1: AI Systems & Agentic Workflow Automation**
> Built by **FentesticFour**

An AI-powered loan processing agent that uses **7 specialized agents** to automate the entire loan lifecycle—from natural language extraction to regulatory compliance and predatory contract detection.

---

## 🏗️ Architecture: The 7-Agent Pipeline

```
User Input (NL Text / Documents)
       │
       ▼
┌───────────────────────────────────────────────┐
│           🤖 Orchestrator Agent                │
│                                               │
│  1. 🔍 Extraction Agent (Gemini 2.0)          │
│     └─ Parses text/files → structured data    │
│                                               │
│  2. ✅ Validation Agent                        │
│     └─ Auto-discovery of missing fields       │
│                                               │
│  3. 📊 Financial Analysis Agent                │
│     └─ DSR & automated risk assessment        │
│                                               │
│  4. 🏦 Credit Check Agent                     │
│     └─ Score & property valuation simulation  │
│                                               │
│  5. ⚖️ Legal Compliance Agent (MCP Mock)       │
│     └─ Verifies local laws (MY/SG/TH/ID)      │
│                                               │
│  6. 📄 Contract Analysis Agent                │
│     └─ SCANS Documents for Legal "Traps"      │
│                                               │
│  7. 🏛️ Decision Engine                        │
│     └─ Final multi-factor verdict             │
└───────────────────────────────────────────────┘
       │
       ▼
  Structured Decision & Safety Report
```

---

## 🌟 New Features (V2.0)

- **Automated Workflow Discovery**: The system no longer naggingly stops for missing info. It processes whatever is available (e.g., checking a contract's safety even before your profile is 100% complete).
- **Legal Compliance (MCP-Ready)**: regional checks for Debt Service Ratio (DSR) caps and minimum income requirements across Malaysia, Singapore, and more.
- **Contract "Trap" Detection**: Upload a loan agreement (PDF, Image, or Text) to scan for hidden fees, predatory late interest, and unfair settlement penalties.
- **Data Synthesis**: Automatic extraction of terms (Principal, Rate, Tenure) from uploaded contracts directly into the user's profile.

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+**
- **pip** (Run `py -m ensurepip` if missing)
- **Google Gemini API Key** (Get one at [aistudio.google.com](https://aistudio.google.com/apikey))

### 1. Install
```powershell
py -m pip install -r requirements.txt
```

### 2. Run
```powershell
py main.py
```
Visit **http://127.0.0.1:8000** to start.

> [!IMPORTANT]
> **GEMINI API KEY REQUIRED FOR DOCUMENTS**: To analyze uploaded contracts and documents, you **MUST** configure your API key in the web app under **Settings (⚙️)**. Without an API key, the system uses a basic regex fallback that cannot "read" files.

---

## 📖 How to Use

### Step 1: Document Upload
Use the **paperclip icon** to upload a contract (like `trap_contract.txt`). The system will:
1. Extract the loan details automatically.
2. Flag any "traps" found in the document.
3. Show the **Safety Score**.

### Step 2: Multi-Country Compliance
Mention your country (e.g., "I'm in Singapore"). The **Legal Compliance Agent** will adjust the DSR limits automatically based on Singaporean regulation.

### Step 3: Full Audit Trace
Expand the **Agent Trace** to see the "thoughts" and duration of all 7 agents involved in the decision.

---

## 🔧 Tech Stack

- **FastAPI**: High-performance backend.
- **Gemini 2.0 Flash**: Multimodal AI for document analysis.
- **Vanilla JS/CSS**: Premium glassmorphic SPA.
- **Pydantic**: Robust data validation.

---

## 👥 Team
**FentesticFour** — UMHackathon 2026
