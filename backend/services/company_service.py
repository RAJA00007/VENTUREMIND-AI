from sqlalchemy.ext.asyncio import AsyncSession

from models.company import Company
from schemas.company import CompanyCreate


async def create_company(
    db: AsyncSession,
    data: CompanyCreate
):

    company = Company(
        name=data.name,
        website=data.website,
        industry=data.industry,
        country=data.country,
    )


    db.add(company)

    await db.commit()

    await db.refresh(company)

    return company