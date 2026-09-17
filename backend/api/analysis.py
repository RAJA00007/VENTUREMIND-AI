import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.dependencies import get_db
from services.analysis_service import analysis_service
from workflows.investment_workflow import investment_graph
from core.security import get_current_user
from models.user import User

from schemas.job import JobCreateResponse
from services.job_service import job_service

router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"]
)

class AnalysisRequest(BaseModel):
    company: str
    company_id: Optional[str] = None
    industry: str = "AI"
    funding: float = 100
    employees: int = 100
    age: int = 3
    revenue: float = 10
    growth: float = 20
    github_repo: Optional[str] = None
    founder_names: Optional[str] = None
    force: bool = False
    sync: bool = False


@router.post("/startup", status_code=202)
async def analyze_startup(
    request: AnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates an asynchronous analysis job for a startup,
    dispatches background agent execution, and returns immediately with a job_id.
    """
    payload = request.model_dump()

    # Optional synchronous override for testing / manual debugging
    if request.sync:
        result = await investment_graph.ainvoke(
            {
                "company": request.company,
                "company_id": request.company_id or request.company,
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
        saved = await asyncio.to_thread(
            analysis_service.save_analysis,
            db=db,
            company_name=request.company,
            agent_results=result["agent_results"],
            committee_result=result["committee_result"],
            user_id=current_user.id
        )
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
            "data_integrity": comm_dict.get("data_integrity", "unverified"),
            "evaluation_status": comm_dict.get("evaluation_status", "complete"),
            "agent_summaries": comm_dict.get("agent_summaries", []),
            "excluded_agents": comm_dict.get("excluded_agents", []),
            "agent_results": {
                k: (v.model_dump() if hasattr(v, "model_dump") else v)
                for k, v in result["agent_results"].items()
            }
        }

    # Standard Asynchronous Analysis Job Flow
    job, is_new = await asyncio.to_thread(
        job_service.create_job,
        db=db,
        user_id=current_user.id,
        request_data=payload,
        force=request.force
    )

    if is_new:
        job_service.start_background_job(job.job_id)

    message = (
        "Analysis job queued successfully."
        if is_new
        else "Active analysis job already in progress for this company."
    )

    return JobCreateResponse(
        job_id=job.job_id,
        status=job.status,
        company_name=job.company_name,
        created_at=job.created_at,
        message=message
    )



@router.get("/history")
async def analysis_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the history of all startup analyses belonging to the current user.
    """
    analyses = await asyncio.to_thread(
        analysis_service.get_all_analyses,
        db,
        user_id=current_user.id
    )
    return analyses


@router.get("/{analysis_id}")
async def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves a single startup analysis by its ID if owned by the current user.
    """
    analysis = await asyncio.to_thread(
        analysis_service.get_analysis_by_id,
        db,
        analysis_id,
        user_id=current_user.id
    )

    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found"
        )

    return analysis