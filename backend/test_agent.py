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



if __name__ == '__main__':
    asyncio.run(main())