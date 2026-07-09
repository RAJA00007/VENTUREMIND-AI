import asyncio

from workflows.investment_workflow import investment_graph


async def main():

    result = await investment_graph.ainvoke(
        {
            "company":"OpenAI",
            "results":[]
        }
    )


    print(result)


asyncio.run(main())