import asyncio

from agents.research_agent import ResearchAgent


async def main():

    agent = ResearchAgent()

    result = await agent.execute(
        {
            "company":"OpenAI"
        }
    )

    print(result)



asyncio.run(main())