from models.analysis import Analysis
from sqlalchemy import select

async def get_all_analyses(
        self,
        db
    ):

        result = await db.execute(
            select(
                Analysis
            )
        )


        return (
            result
            .scalars()
            .all()
        )



async def get_analysis_by_id(
        self,
        db,
        analysis_id:int
    ):


        result = await db.execute(

            select(
                Analysis
            )
            .where(
                Analysis.id == analysis_id
            )

        )


        return (
            result
            .scalar_one_or_none()
        )
        
class AnalysisService:


    async def save_analysis(
        self,
        db,
        company_name,
        results
    ):


        analysis = Analysis(

            company_name=company_name,

            research_result=results[0],

            market_result=results[1],

            competitor_result=results[2],

            risk_result=results[3],

            final_decision=results[-1]

        )


        db.add(
            analysis
        )


        await db.commit()


        await db.refresh(
            analysis
        )


        return analysis



analysis_service = AnalysisService()