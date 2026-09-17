import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.dependencies import get_db
from schemas.company import (
    CompanyCreate,
    CompanyResponse,
)
from services.company_service import create_company
from core.security import get_current_user
from models.user import User

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await asyncio.to_thread(
        create_company,
        db,
        company,
        user_id=current_user.id
    )