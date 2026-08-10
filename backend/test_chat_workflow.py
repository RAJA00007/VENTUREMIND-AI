import asyncio
from workflows.chat_workflow import chat_graph

async def test_chat():
    print("--- Testing QA Intent ---")
    res1 = await chat_graph.ainvoke({
        "messages": [{"role": "user", "content": "What risk metrics do you analyze for startups?"}],
        "intent": "qa_chat",
        "company_name": None,
        "retrieved_rag_context": "",
        "retrieved_db_context": "",
        "retrieved_search_context": "",
        "evaluation_result": None,
        "final_response": ""
    })
    print("Intent:", res1.get("intent"))
    print("Response:\n", res1.get("final_response"))

if __name__ == "__main__":
    asyncio.run(test_chat())
