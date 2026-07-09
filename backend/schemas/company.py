from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CompanyCreate(BaseModel):
    name: str
    website: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None



class CompanyResponse(BaseModel):
    id: int
    name: str
    website: Optional[str]
    industry: Optional[str]
    country: Optional[str]
    created_at: datetime


    class Config:
        from_attributes = True