import os
from typing import TypedDict, List, Annotated
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver
from core.config import settings

# 1. LLM initialized with OpenRouter
llm = ChatOpenAI(
    model="openrouter/free",
    openai_api_key=settings.OPENROUTER_API_KEY,
    openai_api_base="https://openrouter.ai/api/v1",
    streaming=True
)

# 2. State definition with add_messages reducer
class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

def chat_node(state: ChatState):
    messages = state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_edge(START, "chat_node")
graph.add_edge("chat_node", END)

checkpointer = InMemorySaver()
chatbot = graph.compile(checkpointer=checkpointer)

def main():
    print("Testing exact LangGraph chatbot.stream(stream_mode='messages')...")
    config = {"configurable": {"thread_id": "test_thread_1"}}
    
    stream = chatbot.stream(
        {"messages": [HumanMessage(content="Explain IRR in 2 sentences.")]},
        config=config,
        stream_mode="messages"
    )
    
    print("Stream started:")
    for msg, metadata in stream:
        if msg.content:
            print(msg.content, end="", flush=True)
    print("\n[SUCCESS] LangGraph stream finished.")

if __name__ == "__main__":
    main()
