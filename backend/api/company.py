from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from database.dependencies import get_db
from schemas.company import (
    CompanyCreate,
    CompanyResponse,
)
from services.company_service import create_company


router = APIRouter(
    prefix="/companies",
    tags=["Companies"]
)


@router.post(
    "",
    response_model=CompanyResponse
)
async def add_company(
    company: CompanyCreate,
    db: AsyncSession = Depends(get_db)
):

    return await create_company(
        db,
        company
    )