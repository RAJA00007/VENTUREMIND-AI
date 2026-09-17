import asyncio
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.dependencies import get_db
from core.security import get_current_user
from models.user import User
from schemas.job import JobStatusResponse, JobListResponse
from services.job_service import job_service
from services.analysis_service import analysis_service

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the status, progress, and execution stage of an asynchronous analysis job.
    Enforces user ownership: returns 404 if the job does not belong to the authenticated user.
    """
    job = await asyncio.to_thread(
        job_service.get_job,
        db=db,
        job_id=job_id,
        user_id=current_user.id
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Analysis job not found"
        )

    # If completed and linked to an analysis, fetch summary result
    result_data = None
    if job.analysis_id:
        analysis = await asyncio.to_thread(
            analysis_service.get_analysis_by_id,
            db=db,
            analysis_id=job.analysis_id,
            user_id=current_user.id
        )
        if analysis:
            final_dec = analysis.final_decision or {}
            result_data = {
                "analysis_id": analysis.id,
                "company_name": analysis.company_name,
                "created_at": analysis.created_at,
                "category": final_dec.get("category", "HYBRID"),
                "final_score": final_dec.get("final_score", 0.0),
                "verdict": final_dec.get("verdict", "WATCH"),
                "overall_confidence": final_dec.get("overall_confidence", 0.0),
                "data_integrity": final_dec.get("data_integrity", "unverified"),
                "evaluation_status": final_dec.get("evaluation_status", "complete"),
                "agent_results": final_dec.get("agent_results", {})
            }

    return JobStatusResponse(
        job_id=job.job_id,
        company_name=job.company_name,
        company_id=job.company_id,
        status=job.status,
        progress=job.progress,
        current_stage=job.current_stage,
        current_agent=job.current_agent,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        analysis_id=job.analysis_id,
        error_message=job.error_message,
        error_type=job.error_type,
        result=result_data
    )


@router.get("", response_model=JobListResponse)
async def list_user_jobs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists recent analysis jobs for the authenticated user.
    """
    jobs = await asyncio.to_thread(
        job_service.get_user_jobs,
        db=db,
        user_id=current_user.id,
        limit=limit
    )

    items = [
        JobStatusResponse(
            job_id=j.job_id,
            company_name=j.company_name,
            company_id=j.company_id,
            status=j.status,
            progress=j.progress,
            current_stage=j.current_stage,
            current_agent=j.current_agent,
            created_at=j.created_at,
            started_at=j.started_at,
            completed_at=j.completed_at,
            analysis_id=j.analysis_id,
            error_message=j.error_message,
            error_type=j.error_type,
            result=None
        )
        for j in jobs
    ]

    return JobListResponse(jobs=items, total=len(items))
