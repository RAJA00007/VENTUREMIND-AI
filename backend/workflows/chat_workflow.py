import os
from typing import TypedDict, List, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from core.config import settings
from core.logging import app_logger
from services.llm_service import LLMService

def _init_llm():
    if settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip():
        app_logger.info("[Chat Workflow] Initializing ChatOpenAI with Groq (llama-3.3-70b-versatile)")
        return ChatOpenAI(
            model="llama-3.3-70b-versatile",
            openai_api_key=settings.GROQ_API_KEY,
            openai_api_base="https://api.groq.com/openai/v1",
            streaming=True
        )
    if settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY.strip():
        app_logger.info("[Chat Workflow] Initializing ChatOpenAI with OpenRouter")
        return ChatOpenAI(
            model="openrouter/free",
            openai_api_key=settings.OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            streaming=True,
            default_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "VentureMind AI"
            }
        )
    return ChatOpenAI(
        model="llama-3.3-70b-versatile",
        openai_api_key=settings.GROQ_API_KEY or "dummy",
        openai_api_base="https://api.groq.com/openai/v1",
        streaming=True
    )

llm = _init_llm()
llm_service = LLMService()

# 2. Define LangGraph ChatState
class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

SYSTEM_PROMPT = """You are the VentureMind AI Co-Pilot, an intelligent AI Investment Assistant for venture capital due diligence and startup evaluation.
You assist investors, venture capitalists, and analysts by analyzing startup metrics (ARR, CAC/LTV, Burn Rate, Runway, TAM, IRR), evaluating uploaded specs/pitch decks, and explaining investment risk factors.

Provide clear, professional, concise, and structured answers. Use bullet points or numbered lists where appropriate.
If relevant document context from the vector store is provided, incorporate it directly into your analysis."""

# 3. Chat Node
def chat_node(state: ChatState):
    messages = state["messages"]
    user_msg = messages[-1].content if messages else ""
    
    # RAG Context Retrieval
    rag_context = ""
    try:
        from rag.vector_store import vector_store
        results = vector_store.search(user_msg)
        if results and results.get("documents") and results["documents"][0]:
            docs = [doc for doc in results["documents"][0] if doc]
            if docs:
                rag_context = "\n---\n".join(docs[:2])
    except Exception as e:
        app_logger.warning(f"[RAG Retrieval Warning] {e}")

    # Build prompt chain with system prompt + history
    sys_content = SYSTEM_PROMPT
    if rag_context:
        sys_content += f"\n\n[Retrieved RAG Context from Uploaded Documents]:\n{rag_context}"

    full_messages = [SystemMessage(content=sys_content)] + list(messages)

    try:
        response = llm.invoke(full_messages)
    except Exception as e:
        app_logger.error(f"[Chat Node Error] {e}")
        import asyncio
        loop = asyncio.new_event_loop()
        prompt_str = f"{sys_content}\n\nUser Question: {user_msg}"
        reply_text = loop.run_until_complete(llm_service.generate_chat(prompt_str))
        loop.close()
        response = AIMessage(content=reply_text)
    return {"messages": [response]}

# 4. Build LangGraph Workflow with Persistent PostgreSQL Checkpointer
graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_edge(START, "chat_node")
graph.add_edge("chat_node", END)

_checkpointer_cm = None

def _init_checkpointer():
    global _checkpointer_cm
    db_url = getattr(settings, "LANGGRAPH_DATABASE_URL", None) or getattr(settings, "DATABASE_URL", "")
    if not db_url:
        db_url = "postgresql://postgres:admin123@localhost:5432/venturemind"

    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    elif db_url.startswith("postgresql+psycopg://"):
        db_url = db_url.replace("postgresql+psycopg://", "postgresql://")

    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        app_logger.info("[Chat Workflow] Initializing persistent PostgresSaver checkpointer...")
        _checkpointer_cm = PostgresSaver.from_conn_string(db_url)
        cp = _checkpointer_cm.__enter__()
        cp.setup()
        app_logger.info("[Chat Workflow] PostgreSQL checkpointer tables verified successfully!")
        return cp
    except Exception as e:
        app_logger.warning(f"[Chat Workflow] PostgreSQL checkpointer unavailable ({e}) — falling back to MemorySaver")
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()

def close_checkpointer_pool():
    global _checkpointer_cm
    if _checkpointer_cm is not None:
        try:
            cm = _checkpointer_cm
            _checkpointer_cm = None
            cm.__exit__(None, None, None)
            app_logger.info("[Chat Workflow] PostgreSQL checkpointer closed cleanly.")
        except Exception as e:
            app_logger.debug(f"[Chat Workflow] Checkpointer cleanup note: {e}")

checkpointer = _init_checkpointer()
chatbot = graph.compile(checkpointer=checkpointer)

# 5. Stream Generator using stream_mode="messages" with safety fallback
def stream_generator(message: str, thread_id: str = "default_thread"):
    config = {"configurable": {"thread_id": thread_id}}
    yielded_any = False
    try:
        for msg, metadata in chatbot.stream(
            {"messages": [HumanMessage(content=message)]},
            config=config,
            stream_mode="messages"
        ):
            if msg.content:
                yielded_any = True
                yield msg.content
    except Exception as e:
        app_logger.error(f"[Stream Generator Error] {e}")
        if not yielded_any:
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                text = loop.run_until_complete(llm_service.generate_chat(message))
                yield text
            except Exception as fe:
                app_logger.error(f"[Stream Fallback Error] {fe}")
                yield "I encountered an error generating a response. Please try again."
            finally:
                loop.close()

