from typing import Optional, List
from sqlalchemy.orm import Session
from models.company import Company, Founder, FundingRound, CompanyFinancial
from schemas.company import CompanyCreate


def create_company(db: Session, data: CompanyCreate, user_id: Optional[int] = None) -> Company:
    company = Company(
        cin=data.cin,
        company_name=data.company_name,
        legal_name=data.legal_name or data.company_name,
        incorporation_date=data.incorporation_date,
        company_status=data.company_status or "Active",
        company_type=data.company_type,
        registered_state=data.registered_state,
        roc=data.roc,
        dpiit_recognized=data.dpiit_recognized or False,
        dpiit_certificate_number=data.dpiit_certificate_number,
        industry=data.industry,
        sub_industry=data.sub_industry,
        website=data.website,
        source=data.source or "MCA Ingestion",
        source_url=data.source_url,
        confidence_score=data.confidence_score or 1.0,
        created_by_user_id=user_id,
    )

    db.add(company)
    db.flush()

    if data.founders:
        for f in data.founders:
            db.add(Founder(
                company_id=company.id,
                din=f.din,
                name=f.name,
                title=f.title or "Co-Founder",
                linkedin_url=f.linkedin_url,
                github_handle=f.github_handle,
                prior_exits=f.prior_exits or 0
            ))

    if data.funding_rounds:
        for fr in data.funding_rounds:
            db.add(FundingRound(
                company_id=company.id,
                round_type=fr.round_type,
                amount_usd=fr.amount_usd,
                valuation_usd=fr.valuation_usd,
                announced_date=fr.announced_date,
                source=fr.source,
                source_url=fr.source_url
            ))

    if data.financials:
        for fin in data.financials:
            db.add(CompanyFinancial(
                company_id=company.id,
                fiscal_year=fin.fiscal_year,
                revenue_inr=fin.revenue_inr,
                ebitda_inr=fin.ebitda_inr,
                pat_inr=fin.pat_inr,
                burn_rate_monthly=fin.burn_rate_monthly,
                runway_months=fin.runway_months,
                source=fin.source
            ))

    db.commit()
    db.refresh(company)
    return company


def get_company_by_cin(db: Session, cin: str) -> Optional[Company]:
    return db.query(Company).filter(Company.cin == cin).first()


def get_company_by_id(db: Session, company_id: str) -> Optional[Company]:
    return db.query(Company).filter(Company.id == company_id).first()


def list_companies(db: Session, limit: int = 50, offset: int = 0) -> List[Company]:
    return db.query(Company).order_by(Company.created_at.desc()).offset(offset).limit(limit).all()