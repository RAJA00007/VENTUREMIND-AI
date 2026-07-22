import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.session import get_db
from services.analysis_service import analysis_service
from workflows.investment_workflow import investment_graph

router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"]
)

class AnalysisRequest(BaseModel):
    company: str
    industry: str = "AI"
    funding: float = 100
    employees: int = 100
    age: int = 3
    revenue: float = 10
    growth: float = 20
    github_repo: Optional[str] = None
    founder_names: Optional[str] = None


@router.post("/startup")
async def analyze_startup(
    request: AnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Analyzes a startup using the AI agent investment workflow,
    saves the results to the database, and returns the response.
    """

    # ==============================
    # Run AI Agent Workflow
    # ==============================
    result = await investment_graph.ainvoke(
        {
            "company": request.company,
            "industry": request.industry,
            "funding": request.funding,
            "employees": request.employees,
            "age": request.age,
            "revenue": request.revenue,
            "growth": request.growth,
            "github_repo": request.github_repo,
            "founder_names": request.founder_names,
            "agent_results": {},
            "committee_result": None
        }
    )

    # ==============================
    # Save result into Database (Thread Pool)
    # ==============================
    saved = await asyncio.to_thread(
        analysis_service.save_analysis,
        db=db,
        company_name=request.company,
        agent_results=result["agent_results"],
        committee_result=result["committee_result"]
    )

    # ==============================
    # API Response
    # ==============================
    comm = result["committee_result"]
    comm_dict = comm.model_dump() if hasattr(comm, "model_dump") else dict(comm)

    return {
        "id": saved.id,
        "company_name": request.company,
        "created_at": saved.created_at,
        "category": comm_dict.get("category", "HYBRID"),
        "final_score": comm_dict.get("final_score", 0.0),
        "verdict": comm_dict.get("verdict", "WATCH"),
        "overall_confidence": comm_dict.get("overall_confidence", 0.0),
        "was_overridden": comm_dict.get("was_overridden", False),
        "override_reason": comm_dict.get("override_reason"),
        "significant_disagreement": comm_dict.get("significant_disagreement", False),
        "disagreement_note": comm_dict.get("disagreement_note"),
        "key_opportunities": comm_dict.get("key_opportunities", []),
        "key_risks": comm_dict.get("key_risks", []),
        "narrative": comm_dict.get("narrative", ""),
        "confidence_breakdown": comm_dict.get("confidence_breakdown", {}),
        "agent_summaries": comm_dict.get("agent_summaries", []),
        "excluded_agents": comm_dict.get("excluded_agents", []),
        "agent_results": {
            k: (v.model_dump() if hasattr(v, "model_dump") else v)
            for k, v in result["agent_results"].items()
        }
    }


@router.get("/history")
async def analysis_history(
    db: Session = Depends(get_db)
):
    """
    Retrieves the history of all startup analyses from the database.
    """
    analyses = await asyncio.to_thread(
        analysis_service.get_all_analyses,
        db
    )
    return analyses


@router.get("/{analysis_id}")
async def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db)
):
    """
    Retrieves a single startup analysis by its ID.
    """
    analysis = await asyncio.to_thread(
        analysis_service.get_analysis_by_id,
        db,
        analysis_id
    )

    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found"
        )

    return analysis