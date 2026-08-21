import asyncio
from langchain_core.messages import HumanMessage
from workflows.chat_workflow import chatbot, stream_generator

async def test_chat():
    print("--- Testing Chatbot LangGraph Workflow with LangSmith Tracing ---")
    config = {"configurable": {"thread_id": "test_thread_1"}}
    res1 = await chatbot.ainvoke({
        "messages": [HumanMessage(content="What risk metrics do you analyze for startups?")]
    }, config=config)
    print("Response Messages:")
    for msg in res1.get("messages", []):
        print(f"[{msg.type}]: {msg.content}")

    print("\n--- Testing Stream Generator ---")
    for chunk in stream_generator("Briefly summarize investment criteria."):
        print(chunk, end="", flush=True)
    print()

if __name__ == "__main__":
    asyncio.run(test_chat())
