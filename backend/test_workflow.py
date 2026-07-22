import asyncio

from workflows.investment_workflow import investment_graph


async def main():

    result = await investment_graph.ainvoke(
        {
            "company": "OpenAI",
            "industry": "AI",
            "funding": 10000.0,
            "employees": 500,
            "age": 11,
            "revenue": 2000.0,
            "growth": 100.0,
            "github_repo": "openai/openai-python",
            "founder_names": "Sam Altman, Greg Brockman",
            "agent_results": {},
            "committee_result": None
        }
    )


    print(result)


if __name__ == '__main__':
    asyncio.run(main())