from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AnalysisRequest(BaseModel):

    company: str



class AnalysisResponse(BaseModel):

    id: int

    company_name: str

    final_decision: Any

    created_at: datetime


    class Config:
        from_attributes = True