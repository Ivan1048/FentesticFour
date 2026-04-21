# LoanFlow AI – Intelligent Loan Processing System

A hackathon demo showcasing **multi-agent AI coordination** for end-to-end loan application processing.  
Built with **FastAPI + PostgreSQL + HTMX** (responsive mobile + laptop).

---

## ✨ Features

- **Multi-step stateful workflow**: INTAKE → VALIDATE → ANALYZE → EXTERNAL_CHECKS → DECISION → DONE
- **Multi-agent coordination**: Intake · Underwriter · Verification · Comms agents with distinct roles
- **Deterministic DSR engine**: calculates Debt-Service Ratio and affordability automatically
- **Simulated external tools**: credit score check + property valuation (with failure modes)
- **Structured JSON output**: `loan_status`, `risk_level`, `dsr`, `missing_information`, `next_action`
- **Professional NL reply** from Comms agent
- **Provider-agnostic agent interface**: `MockAgentClient` works today; swap in `ZaiAgentClient` tomorrow
- **Responsive HTMX UI**: works on mobile phones and laptops

---

## 🚀 Quick Start (Docker Compose)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker + Docker Compose)

### 1. Clone and start

```bash
git clone https://github.com/Ivan1048/FentesticFour.git
cd FentesticFour
docker compose up --build
```

The first build takes ~2 minutes. After that:

| Service | URL |
|---------|-----|
| **App (landing page)** | http://localhost:8000/ |
| **API docs (Swagger)** | http://localhost:8000/docs |
| **PostgreSQL** | localhost:5432 |

### 2. Open the app

Go to **http://localhost:8000** → click **"Start AI Assessment"** → chat with the AI loan officer!

---

## 🛠 Local Development (without Docker)

### Prerequisites
- Python 3.12+
- PostgreSQL running locally

### Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set database URL
export DATABASE_URL="postgresql://loanuser:loanpass@localhost:5432/loandb"

# 3. Create database (if not exists)
createdb loandb
psql loandb -c "CREATE USER loanuser WITH PASSWORD 'loanpass';"
psql loandb -c "GRANT ALL PRIVILEGES ON DATABASE loandb TO loanuser;"

# 4. Run the server
uvicorn backend.main:app --reload --port 8000
```

---

## 🤖 Switching to Z.Ai Provider

1. Set environment variables:

```bash
export AGENT_PROVIDER=zai
export ZAI_API_BASE=https://api.z.ai/v1
export ZAI_API_KEY=your_key_here
export ZAI_MODEL=zai-default
```

2. In Docker Compose, uncomment the Z.Ai variables in `docker-compose.yml` and set `AGENT_PROVIDER=zai`.

The `ZaiAgentClient` in `backend/agent/zai.py` mirrors the OpenAI-compatible chat completion API.  
No UI or workflow changes needed — just swap the provider.

---

## 🧪 Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

35 tests covering:
- DSR calculations (amortisation formula, boundary conditions)
- Affordability assessment (DSR thresholds: <40% low, 40–60% medium, >60% high)
- Policy decision rules (approved/rejected/manual review/incomplete)
- Mock agent responses (intake extraction, underwriting, verification, comms)

---

## 📁 Project Structure

```
FentesticFour/
├── backend/
│   ├── main.py           # FastAPI app + HTML routes + API endpoints
│   ├── schemas.py        # Pydantic models
│   ├── workflow.py       # State machine (INTAKE→DONE)
│   ├── storage.py        # PostgreSQL persistence (asyncpg)
│   ├── tools/
│   │   ├── dsr.py        # DSR + affordability calculations
│   │   ├── policy.py     # Decision rules
│   │   ├── credit.py     # Simulated credit score check
│   │   └── valuation.py  # Simulated property valuation
│   └── agent/
│       ├── base.py       # AgentClient abstract interface
│       ├── mock.py       # MockAgentClient (works offline)
│       └── zai.py        # Z.Ai provider stub
├── frontend/
│   └── templates/
│       ├── index.html    # Landing page
│       └── app.html      # Application console (chat + decision panel)
├── tests/
│   ├── test_workflow_policy.py   # DSR + policy unit tests
│   └── test_mock_agent.py        # Agent integration tests
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## 📊 DSR Decision Rules

| DSR Range | Risk Level | Decision |
|-----------|-----------|----------|
| < 40% | Low | ✅ Approved |
| 40% – 60% | Medium | 🟡 Manual Review |
| > 60% | High | ❌ Rejected |

---

## 🔑 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/applications` | Create new loan application |
| `GET` | `/api/applications/{id}` | Fetch full application state |
| `POST` | `/api/applications/{id}/messages` | Send message, advance workflow |

### Query parameters for `/messages`:
- `simulate_credit_failure=true` – test credit bureau failure mode
- `simulate_valuation_failure=true` – test property valuation failure mode

