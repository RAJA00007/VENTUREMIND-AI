from sqlalchemy.orm import Session
from models.company import Company
from schemas.company import CompanyCreate

def create_company(
    db: Session,
    data: CompanyCreate
):
    company = Company(
        name=data.name,
        website=data.website,
        industry=data.industry,
        country=data.country,
    )

    db.add(company)
    db.commit()
    db.refresh(company)
    return company