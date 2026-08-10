from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field


class FounderSchema(BaseModel):
    din: Optional[str] = None
    name: str
    title: Optional[str] = "Co-Founder"
    linkedin_url: Optional[str] = None
    github_handle: Optional[str] = None
    prior_exits: Optional[int] = 0


class FundingRoundSchema(BaseModel):
    round_type: str
    amount_usd: Optional[float] = None
    valuation_usd: Optional[float] = None
    announced_date: Optional[date] = None
    source: Optional[str] = None
    source_url: Optional[str] = None


class CompanyFinancialSchema(BaseModel):
    fiscal_year: str
    revenue_inr: Optional[float] = None
    ebitda_inr: Optional[float] = None
    pat_inr: Optional[float] = None
    burn_rate_monthly: Optional[float] = None
    runway_months: Optional[int] = None
    source: Optional[str] = None


class CompanyCreate(BaseModel):
    company_name: str
    legal_name: Optional[str] = None
    cin: Optional[str] = None
    incorporation_date: Optional[date] = None
    company_status: Optional[str] = "Active"
    company_type: Optional[str] = "Private Limited"
    registered_state: Optional[str] = None
    roc: Optional[str] = None
    dpiit_recognized: Optional[bool] = False
    dpiit_certificate_number: Optional[str] = None
    industry: Optional[str] = None
    sub_industry: Optional[str] = None
    website: Optional[str] = None
    source: Optional[str] = "MCA Ingestion"
    source_url: Optional[str] = None
    confidence_score: Optional[float] = 1.0
    founders: Optional[List[FounderSchema]] = []
    funding_rounds: Optional[List[FundingRoundSchema]] = []
    financials: Optional[List[CompanyFinancialSchema]] = []


class CompanyResponse(BaseModel):
    id: str
    cin: Optional[str] = None
    company_name: str
    legal_name: str
    incorporation_date: Optional[date] = None
    company_status: str
    company_type: Optional[str] = None
    registered_state: Optional[str] = None
    roc: Optional[str] = None
    dpiit_recognized: bool = False
    dpiit_certificate_number: Optional[str] = None
    industry: Optional[str] = None
    sub_industry: Optional[str] = None
    website: Optional[str] = None
    source: str
    source_url: Optional[str] = None
    confidence_score: float = 1.0
    last_verified_at: datetime
    created_at: datetime
    updated_at: datetime
    founders: List[FounderSchema] = []
    funding_rounds: List[FundingRoundSchema] = []
    financials: List[CompanyFinancialSchema] = []

    class Config:
        from_attributes = True