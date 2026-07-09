from typing import Any
from models.analysis import Analysis
from sqlalchemy import select

class AnalysisService:

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
        analysis_id: int
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

    async def save_analysis(
        self,
        db,
        company_name,
        agent_results: dict,
        committee_result: Any
    ):
        # Extract individual agents
        research = agent_results.get("Research Agent")
        market = agent_results.get("Market Agent")
        competitor = agent_results.get("Competitor Agent")
        risk = agent_results.get("Risk Agent")

        # Serialize to dict/json if they are Pydantic models
        research_dict = research.model_dump() if hasattr(research, "model_dump") else research
        market_dict = market.model_dump() if hasattr(market, "model_dump") else market
        competitor_dict = competitor.model_dump() if hasattr(competitor, "model_dump") else competitor
        risk_dict = risk.model_dump() if hasattr(risk, "model_dump") else risk
        
        # Serialize the committee result and embed the full agent results for convenience in history view
        committee_dict = committee_result.model_dump() if hasattr(committee_result, "model_dump") else dict(committee_result)
        # Store full agent_results inside committee dict so history page can access all factors easily
        committee_dict["agent_results"] = {
            k: (v.model_dump() if hasattr(v, "model_dump") else v)
            for k, v in agent_results.items()
        }

        analysis = Analysis(
            company_name=company_name,
            research_result=research_dict,
            market_result=market_dict,
            competitor_result=competitor_dict,
            risk_result=risk_dict,
            final_decision=committee_dict
        )

        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)
        return analysis

analysis_service = AnalysisService()