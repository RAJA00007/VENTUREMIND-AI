# 🧠 VentureMind AI

**VentureMind AI** is an AI-powered venture due diligence platform that performs comprehensive startup analysis using a deterministic multi-agent architecture built with **LangGraph**, **LangChain**, and **FastAPI**.

Instead of relying on a single LLM response, VentureMind AI coordinates multiple specialized AI agents that independently evaluate different aspects of a startup, including founders, market, competition, finance, technical quality, risks, and predictive signals, before a **Committee Agent** synthesizes the results into a transparent investment recommendation.

The platform emphasizes **explainability**, **deterministic scoring**, and **evidence-backed decision making**, making it suitable for investors, accelerators, venture studios, incubators, and startup evaluation teams.

---

# 🚀 Current Project Status

The project has progressed beyond initial scaffolding and now includes the core multi-agent architecture, deterministic scoring engine, business classification system, and shared evaluation contracts.

Implemented components include:

---

# 🏗 Backend Infrastructure

### FastAPI Backend

- FastAPI application with startup lifecycle events
- Root endpoint exposing application metadata
- Health monitoring endpoint
- Async-ready architecture

### Configuration

- Environment variables managed via **Pydantic Settings**
- `.env.example` template included
- Secure API key management

### Logging

- Structured logging using **Loguru**
- Colorized console logs
- Centralized logging configuration

### Global Constants

- API versioning
- Request timeout configuration
- Retry policies
- Shared project constants

---

# 🗄 Database Layer

Built using **SQLAlchemy 2.0 Async**.

Includes:

- Async PostgreSQL engine
- Session management
- Declarative models
- Alembic migrations
- Async migration environment

---

# 🤖 Multi-Agent Architecture

The platform follows a cooperative agent-based architecture powered by LangGraph.

Each agent has a single responsibility.

## 🔍 Research Agent

Responsible for collecting publicly available information about a company.

Extracts:

- Company overview
- Business model
- Industry
- Funding information
- Public evidence
- Company metadata

ResearchAgent focuses only on gathering evidence and never makes investment decisions.

---

## 🏢 Company Classifier

A deterministic classification component that categorizes startups into:

- TECH
- HYBRID
- NON_TECH

Unlike traditional LLM classification, the model **does not allow the LLM to directly choose the category**.

Instead:

LLM extracts structured business facts:

- Is the core product software?
- Is revenue primarily generated through physical goods?

A deterministic Python decision rule then assigns the business profile.

This ensures reproducible and explainable weighting decisions.

---

## 📊 Market Agent

Evaluates:

- TAM
- SAM
- SOM
- Market growth
- Industry maturity
- Customer demand
- Market attractiveness

---

## 🥊 Competitor Agent

Analyzes:

- Competitor landscape
- Competitive advantages
- Product differentiation
- Defensibility
- Market positioning

---

## 👥 Founder Agent

Evaluates founders using publicly available evidence.

Includes:

- Professional background
- Startup experience
- Leadership
- Team execution capability
- Domain expertise

---

## 💻 GitHub Agent

Performs technical due diligence.

Evaluates:

- Repository quality
- Project architecture
- Code quality
- Commit activity
- Contributor health
- Technical debt
- Documentation

For non-technical companies, GitHub analysis is still performed when possible, but receives lower or zero weight during final scoring depending on the selected business profile.

---

## 💰 Finance Agent

Performs financial due diligence.

Evaluates:

- Business model
- Revenue model
- Unit economics
- Burn rate
- Financial health
- Growth projections
- Funding history
- Investor quality

Investor ROI or proprietary VC performance metrics are intentionally excluded to maintain deterministic scoring using publicly available evidence.

---

## ⚠ Risk Agent

Identifies:

- Operational risks
- Financial risks
- Legal risks
- Market risks
- SWOT factors

Acts as a risk modifier within the final committee evaluation.

---

## 📈 Prediction Agent

Provides an AI-based predictive signal regarding startup potential.

This prediction is treated as a supplementary signal rather than the primary investment decision.

---

## 🧠 Committee Agent

The Committee Agent is the final decision-making component.

It **does not perform research**.

Instead, it:

- Collects results from every specialized agent
- Selects the appropriate weight profile
- Applies deterministic weighted scoring
- Aggregates confidence values
- Produces the final investment recommendation
- Generates an explainable evaluation report

---

# ⚖ Deterministic Scoring Engine

A centralized scoring engine ensures every evaluation follows identical mathematical rules.

Each specialized agent returns a standardized `AgentScoreResult` containing:

- Score (0-100)
- Confidence
- Evidence
- Score factors
- Reasoning
- Status

The Committee Agent combines these using deterministic weighted scoring.

---

# 🏢 Dynamic Business Profiles

Weighting changes based on company type.

### TECH

Optimized for:

- AI
- SaaS
- Developer tools
- Software products

Greater emphasis on:

- GitHub quality
- Technical execution

---

### HYBRID

Optimized for:

- FinTech
- HealthTech
- Consulting
- Marketplaces
- Enterprise platforms

Balanced weighting across business and technology.

---

### NON_TECH

Optimized for:

- D2C
- FMCG
- Retail
- Consumer products
- Manufacturing

Greater emphasis on:

- Market
- Finance
- Competition

Technical code quality has minimal impact on the final investment score.

---

# 📊 Shared Scoring Contracts

A centralized scoring module standardizes communication between all agents.

Features include:

- Shared scoring schema
- Validation
- Confidence normalization
- Business profile models
- Score factor definitions
- Failure handling
- Explainable score breakdown

This allows every agent to communicate using the same interface.

---

# 🔄 LangGraph Workflow

The system follows a workflow similar to:

```text
Start
  |
Research Agent
  |
Company Classifier
  |
-------- Parallel Execution --------
|        |         |        |
Market Founder Finance GitHub
|        |         |        |
Competitor Risk Prediction
--------------+--------------
          |
    Committee Agent
          |
     Final Evaluation
          |
         End
```

---

# 📂 Repository Structure

```text
venturemind-ai/
|- backend/
|  |- agents/
|  |- workflows/
|  |- tools/
|  |- services/
|  |- database/
|  |- models/
|  |- schemas/
|  |- api/
|  |- core/
|  |- utils/
|  |- tests/
|  |- main.py
|  \- requirements.txt
|- frontend/
|- docs/
|- LICENSE
\- README.md
```

---

# 🛠 Technology Stack

### Backend

- Python 3.11+
- FastAPI
- LangChain
- LangGraph
- Pydantic v2
- SQLAlchemy 2.0
- AsyncPG
- Alembic
- Loguru

### AI & LLM

- OpenAI
- LangChain
- LangGraph

### Search & Research

- Tavily Search API
- HTTPX

### Database

- PostgreSQL
- SQLAlchemy Async

### Testing

- Pytest

---

# 🎯 Design Principles

- Deterministic scoring over subjective LLM opinions
- Explainable AI decisions
- Modular multi-agent architecture
- Shared scoring contracts
- Dynamic business-aware weighting
- Separation of responsibilities
- Confidence-aware evaluation
- Extensible workflow using LangGraph

---

# 📌 Roadmap

- Shared RAG knowledge base for evidence retrieval
- Vector database integration (Qdrant/Chroma)
- Real-time startup monitoring
- PDF investment committee reports
- Historical startup comparison
- Portfolio analytics dashboard
- Investor watchlists
- Batch company evaluation
- API integrations (Crunchbase, LinkedIn, GitHub, SEC filings)
- Multi-model LLM support
- Human-in-the-loop review workflow
