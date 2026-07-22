import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

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
    db: Session = Depends(get_db)
):
    return await asyncio.to_thread(
        create_company,
        db,
        company
    )