# VentureMind AI — Complete System Context & Architecture Guide

This document serves as the authoritative context file for AI agents (and human developers) working on the **VentureMind AI** codebase.

---

## 1. System Overview

**VentureMind AI** is an Autonomous Venture Capital Due Diligence & Startup Intelligence Platform. Unlike generic chat assistants, it operates as an automated investment committee with 8 domain-specialized scoring agents and 1 synthesis agent.

### Key Architectural Principles:
1. **Rubric-Gated Scoring (0–100 Scale)**: Every agent evaluates startups against explicit rubrics with fixed point maximums.
2. **Deterministic Synthesis**: The Investment Committee score is calculated via code using fixed weight profiles (`TECH`, `NON_TECH`, `HYBRID`), eliminating black-box LLM score fabrication.
3. **LLM Provider Failover Chain**: Resilient failover chain:
   **Gemini 2.0 Flash** ➔ **Groq Llama 3.3 70B** ➔ **OpenRouter Free** ➔ **Cerebras AI** ➔ **Together AI** ➔ **DeepSeek AI** ➔ **Local Ollama LLM** ➔ **Gated Mock Fallback**.
4. **Lazy Client Instantiation**: All API clients initialize lazily to prevent module import crashes if keys are absent or rate-limited.
5. **Trust & Safety Controls**: Disagreement detection (surfacing high score variance between agents) and confidence capping (preventing unconfident data from generating an "INVEST" verdict).

---

## 2. Directory Structure & Key Files

```text
venturemind-ai/
├── PROJECT_CONTEXT.md              # Complete AI Agent Context & Guide (This File)
├── README.md                       # High-level overview & quickstart
├── requirements.txt                # Python dependencies
│
├── backend/
│   ├── main.py                     # FastAPI application entry point & CORS
│   ├── .env                        # Environment variables (API keys & flags)
│   ├── core/
│   │   ├── config.py               # Pydantic BaseSettings & dynamic .env path resolution
│   │   ├── constants.py            # Weight profiles, timeouts, and scoring constants
│   │   ├── cache.py                # SQLite / Redis cache manager for LLM & search
│   │   └── logging.py              # Structured application logger
│   │
│   ├── agents/                     # The 9 Autonomous AI Agents
│   │   ├── base_agent.py           # Abstract BaseAgent with error isolation & retries
│   │   ├── research_agent.py       # Baseline vision, founders, traction analyst (0-100)
│   │   ├── market_agent.py         # TAM, SAM, CAGR growth analyst (0-100)
│   │   ├── competitor_agent.py     # Competitor landscape & moat analyst (0-100)
│   │   ├── founder_agent.py        # Founder track record & domain fit analyst (0-100)
│   │   ├── finance_agent.py        # ARR, unit economics, runway analyst (0-100)
│   │   ├── github_agent.py         # Code quality & repo health analyst (0-100 deterministic)
│   │   ├── risk_agent.py           # Independent red-flag & legal risk analyst (0-100, high=safe)
│   │   ├── prediction_agent.py     # Feature extraction & ML success probability (0-100)
│   │   ├── committee_agent.py      # Final synthesis, verdict & narrative author
│   │   ├── company_classifier.py   # Decision-tree classifier (TECH / NON_TECH / HYBRID)
│   │   └── scoring_formula.py      # Pure deterministic weighted score calculator
│   │
│   ├── services/
│   │   ├── llm_service.py          # Resilient multi-provider LLM client with failover & mock
│   │   ├── trust_service.py        # Disagreement detection & verdict safety rules
│   │   └── analysis_service.py     # DB persistence service for evaluation runs
│   │
│   ├── tools/
│   │   ├── search_tool.py          # Tavily search wrapper with cache & lazy client
│   │   └── github_tool.py          # GitHub REST API client for repo metrics
│   │
│   ├── workflows/
│   │   └── investment_workflow.py  # LangGraph StateGraph orchestration pipeline
│   │
│   ├── database/
│   │   ├── session.py              # SQLAlchemy engine with SQLite fallback & auto-table creation
│   │   ├── base.py                 # DeclarativeBase model foundation
│   │   └── database.py             # Async engine definition
│   │
│   ├── scripts/
│   │   └── run_agents_one_by_one.py# Terminal script running all 9 agents sequentially with logs
│   │
│   ├── test_workflow.py            # LangGraph workflow verification script
│   └── test_multi_agent.py         # Multi-agent integration verification script
│
└── venturemind-frontend/
    └── venturemind/                # Frontend web application (HTML/CSS/JS dashboard)
        ├── index.html              # Landing page
        ├── dashboard.html          # Interactive investment hub dashboard
        ├── login.html              # Auth page
        ├── css/                    # Custom CSS styling & themes
        └── js/                     # API integration & chart rendering scripts
```

---

## 3. Agent Responsibilities & Rubrics

| Agent | Responsibilities | Output Contract | Key Method |
| :--- | :--- | :--- | :--- |
| **Research Agent** | Evaluates vision, company overview, founder credibility, product maturity, and initial traction. | `AgentScoreResult` (0-100) | Web search + LLM Rubric |
| **Market Agent** | Evaluates TAM/SAM size, CAGR growth rate, customer demand, and timing tailwinds. | `AgentScoreResult` (0-100) | Web search + LLM Rubric |
| **Competitor Agent** | Maps competitive landscape, moat defensibility, and competitive risk exposure. | `AgentScoreResult` (0-100) | Web search + LLM Rubric |
| **Founder Agent** | Assesses domain experience, prior exit track record, team balance, and shipment speed. | `AgentScoreResult` (0-100) | Web search + LLM Rubric |
| **Finance Agent** | Analyzes ARR, unit economics, runway, VC backing quality, and financial red flags. | `AgentScoreResult` (0-100) | Web search + LLM Rubric |
| **Code / GitHub Agent** | Scores commit recency, contributor bus factor, CI/CD, test dirs, and star traction. | `AgentScoreResult` (0-100) | **Deterministic GitHub API** |
| **Risk Agent** | Searches for lawsuits, regulatory scrutiny, negative press, and cross-checks sibling findings. | `AgentScoreResult` (0-100) | Independent Red-Flag Search |
| **Prediction Agent** | Extracts 6 firmographic features and passes them to an ML probability model. | `AgentScoreResult` (0-100) | Feature Extraction + ML |
| **Committee Agent** | Selects weight profile via classifier, applies `combine_scores()`, enforces safety, and writes narrative. | `CommitteeResult` | Code Formula + LLM Prose |

---

## 4. Weight Profiles & Deterministic Scoring Formula

Score calculation is **100% deterministic** in `backend/agents/scoring_formula.py`:

$$\text{Final Score} = \frac{\sum (W_i \times S_i)}{\sum W_i}$$

Where weights ($W_i$) depend on the classified company category:

| Agent | TECH Weight | NON_TECH Weight | HYBRID Weight |
| :--- | :---: | :---: | :---: |
| **Research Agent** | 10% | 15% | 15% |
| **Market Agent** | 15% | 25% | 20% |
| **Competitor Agent** | 15% | 15% | 15% |
| **Founder Agent** | 15% | 20% | 15% |
| **Finance Agent** | 15% | 15% | 15% |
| **Code / GitHub Agent**| 15% | 0% (Excluded) | 5% |
| **Risk Agent** | 10% | 10% | 10% |
| **Prediction Agent** | 5% | 0% (Excluded) | 5% |

---

## 5. Execution & CLI Commands

### Run Full LangGraph Workflow Test:
```powershell
.\.venv\Scripts\python.exe backend/test_workflow.py
```

### Run All 9 Agents Sequentially on Terminal (Detailed Logs):
```powershell
.\.venv\Scripts\python.exe backend/scripts/run_agents_one_by_one.py
```

### Start Live Backend Server (Port 8000):
```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### Start Frontend Server (Port 3000):
```powershell
python -m http.server 3000 --directory venturemind-frontend/venturemind
```

---

## 6. Environment Configuration (`backend/.env`)

```env
APP_NAME=VentureMind AI
APP_VERSION=1.0.0
DEBUG=True

OPENAI_API_KEY=dummy
TAVILY_API_KEY=tvly-dev-...
GEMINI_API_KEY=AQ.Ab8RN6...
DATABASE_URL=postgresql+asyncpg://postgres:postgres123@localhost:5432/venturemind
GROQ_API_KEY=gsk_FoPe5l...
OPENROUTER_API_KEY=sk-or-v1-...
ALLOW_MOCK_FALLBACK=True
```

---

## 7. Directives for AI Agents Modifying This Repo

1. **Never break `BaseAgent` Contract**: All agents must inherit `BaseAgent` and return `AgentScoreResult` (except `CommitteeAgent` which returns `CommitteeResult`).
2. **No Eager Client Instantiations**: Always use `@property` lazy instantiation for external API clients in `llm_service.py` and `search_tool.py`.
3. **Preserve Error Isolation**: Never allow exceptions inside an individual agent `run()` method to propagate uncaught — `execute()` must return a valid degraded `AgentScoreResult` with status `"failed"` or `"no_data"`.
4. **Use `.venv` for Python Commands**: Always run terminal python scripts using `.venv\Scripts\python.exe`.

---

## 8. Today's Completed Work Log

### A. LangGraph Chatbot Workflow & Streaming System
- **StateGraph & Memory**: Integrated LangGraph chatbot workflow ([`chat_workflow.py`](file:///c:/Users/Raja/venturemind-ai/backend/workflows/chat_workflow.py)) using `StateGraph(ChatState)` with `InMemorySaver` memory checkpointer and `add_messages` reducer to persist thread history.
- **Groq Primary Engine**: Standardized LLM initialization on Groq (`llama-3.3-70b-versatile`) with automatic multi-provider fallback.
- **RAG Integration**: Integrated ChromaDB vector store search (`startup_docs`) into `chat_node` to query uploaded pitch decks/specs and incorporate document context directly into replies.
- **VentureMind Co-Pilot Persona**: Configured SystemMessage persona specializing in VC due diligence, financial metrics (ARR, CAC/LTV, Burn Rate, Runway, TAM, IRR), and risk analysis.

### B. Dual-Mode API Endpoints & Frontend Safety
- **Dual Endpoints ([`chat.py`](file:///c:/Users/Raja/venturemind-ai/backend/api/chat.py))**:
  - `POST /api/v1/chat`: Standard REST JSON endpoint returning `{ "response": "...", "thread_id": "..." }`.
  - `POST /api/v1/chat/stream`: Event-stream endpoint (`text/event-stream`) returning real-time streaming chunks.
- **Frontend Fail-Safe ([`dashboard.js`](file:///c:/Users/Raja/venturemind-ai/venturemind-frontend/venturemind/js/dashboard.js))**:
  - Implemented `Content-Type` header inspection to read both JSON responses and stream readers safely.
  - Sanitized exception catch blocks to prevent raw V8 `SyntaxError` strings (e.g., `Unexpected token 'H'...`) from ever rendering in chat bubbles.

### C. Company Data & Ingestion Architecture
- **Data Models ([`backend/models/company.py`](file:///c:/Users/Raja/venturemind-ai/backend/models/company.py))**:
  - Built comprehensive SQLAlchemy model for `Company` including MCA attributes (`cin`, `legal_name`, `incorporation_date`, `roc`, `registered_state`, `company_status`, `company_type`), DPIIT startup recognition (`dpiit_recognized`, `dpiit_certificate_number`), and source audit fields (`source`, `source_url`, `confidence_score`, `last_verified_at`).
  - Implemented normalized child entity models: `Founder`, `FundingRound`, and `CompanyFinancial`.
- **Pydantic Schemas ([`backend/schemas/company.py`](file:///c:/Users/Raja/venturemind-ai/backend/schemas/company.py))**:
  - Added type-safe Pydantic models: `CompanyCreate`, `CompanyResponse`, `FounderSchema`, `FundingRoundSchema`, and `CompanyFinancialSchema`.
- **Persistence Service ([`backend/services/company_service.py`](file:///c:/Users/Raja/venturemind-ai/backend/services/company_service.py))**:
  - Added transactional entity creation & retrieval functions: `create_company()`, `get_company_by_cin()`, `get_company_by_id()`, and `list_companies()`.

