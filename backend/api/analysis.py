from fastapi import APIRouter

from pydantic import BaseModel

from workflows.investment_workflow import investment_graph
from fastapi import HTTPException

from fastapi import Depends

from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_db

from services.analysis_service import analysis_service

router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"]
)



class AnalysisRequest(BaseModel):

    company: str

    industry: str = "AI"

    funding: float = 100

    employees: int = 100

    age: int = 3

    revenue: float = 10

    growth: float = 20





@router.post(
    "/startup"
)
async def analyze_startup(

    request: AnalysisRequest,

    db: AsyncSession = Depends(get_db)

):
    """
    Analyzes a startup using the AI agent investment workflow,
    saves the results to the database, and returns the response.
    """

    # ==============================
    # Run AI Agent Workflow
    # ==============================

    result = await investment_graph.ainvoke(
        {

            "company": request.company,

            "industry": request.industry,

            "funding": request.funding,

            "employees": request.employees,

            "age": request.age,

            "revenue": request.revenue,

            "growth": request.growth,

            "results": []

        }
    )



    # ==============================
    # Save result into PostgreSQL
    # ==============================

    saved = await analysis_service.save_analysis(

        db=db,

        company_name=request.company,

        results=result["results"]

    )



    # ==============================
    # API Response
    # ==============================

    return {

        "id": saved.id,

        "company": request.company,

        "analysis": result["results"]

    }


@router.get(
    "/history"
)
async def analysis_history(

    db: AsyncSession = Depends(get_db)

):
    """
    Retrieves the history of all startup analyses from the database.
    """


    analyses = await analysis_service.get_all_analyses(
        db
    )


    return analyses



@router.get(
    "/{analysis_id}"
)
async def get_analysis(

    analysis_id:int,

    db: AsyncSession = Depends(get_db)

):
    """
    Retrieves a single startup analysis by its ID.
    """


    analysis = await analysis_service.get_analysis_by_id(

        db,

        analysis_id

    )


    if not analysis:

        raise HTTPException(

            status_code=404,

            detail="Analysis not found"

        )


    return analysis