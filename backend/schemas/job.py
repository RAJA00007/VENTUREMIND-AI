from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class JobCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: str = "queued"
    company_name: str
    created_at: datetime
    message: str = "Analysis job queued successfully."


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    company_name: str
    company_id: Optional[str] = None
    status: str
    progress: int
    current_stage: Optional[str] = None
    current_agent: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    analysis_id: Optional[int] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class JobListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    jobs: List[JobStatusResponse]
    total: int
