import asyncio

from agents.research_agent import ResearchAgent
from agents.market_agent import MarketAgent
from agents.competitor_agent import CompetitorAgent
from agents.risk_agent import RiskAgent



async def main():

    startup = {
        "company":"OpenAI"
    }


    agents = [
        ResearchAgent(),
        MarketAgent(),
        CompetitorAgent(),
    ]


    results=[]


    for agent in agents:

        result = await agent.execute(
            startup
        )

        results.append(result)



    risk = RiskAgent()

    risk_result = await risk.execute(
        {
            "company": startup["company"],
            "other_findings": {r.agent: r for r in results}
        }
    )


    results.append(risk_result)


    print(results)



if __name__ == '__main__':
    asyncio.run(main())