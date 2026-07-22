import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from services.llm_service import llm_service, AllLLMProvidersFailedError
from rag.vector_store import vector_store
from core.logging import app_logger
from core.config import settings

router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

@router.post("")
async def chat_assistant(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="No conversation messages provided.")

    # Get the last user message to query vector database context
    last_user_message = request.messages[-1].content
    
    # Check if the user is requesting a live evaluation
    eval_match = re.search(
        r"\b(evaluate|analyze|run analysis on)\s+['\"]?([a-zA-Z0-9.\- ]+)['\"]?",
        last_user_message,
        re.IGNORECASE
    )
    if eval_match:
        company_name = eval_match.group(2).strip()
        app_logger.info(f"[Chat Endpoint] User requested live analysis for: {company_name}")
        from workflows.investment_workflow import investment_graph
        from services.analysis_service import analysis_service
        from database.session import AsyncSessionLocal
        try:
            result = await investment_graph.ainvoke({
                "company": company_name,
                "industry": "AI",
                "funding": 0.0,
                "employees": 0,
                "age": 0,
                "revenue": 0.0,
                "growth": 0.0,
                "github_repo": None,
                "founder_names": None,
                "agent_results": {},
                "committee_result": None
            })
            
            async with AsyncSessionLocal() as session:
                saved = await analysis_service.save_analysis(
                    db=session,
                    company_name=company_name,
                    agent_results=result["agent_results"],
                    committee_result=result["committee_result"]
                )
            
            comm = result["committee_result"]
            comm_dict = comm.model_dump() if hasattr(comm, "model_dump") else dict(comm)
            
            response_text = (
                f"I have completed a full multi-agent investment evaluation for **{company_name}**.\n\n"
                f"**Final Verdict**: {comm_dict.get('verdict', 'WATCH')} | "
                f"**Investment Score**: {comm_dict.get('final_score', 0.0)}/100 | "
                f"**Confidence**: {comm_dict.get('overall_confidence', 0.0):.2f}\n\n"
                f"**Executive Synthesis**:\n{comm_dict.get('narrative', '')}\n\n"
                f"**Key Opportunities**:\n" + "\n".join([f"- {opt}" for opt in comm_dict.get("key_opportunities", [])]) + "\n\n"
                f"**Key Risks**:\n" + "\n".join([f"- {risk}" for risk in comm_dict.get("key_risks", [])]) + "\n\n"
                f"*(Note: This analysis report has been saved to the archive with ID {saved.id}.)*"
            )
            return {"content": response_text}
        except Exception as exc:
            app_logger.error(f"[Chat Endpoint] Failed to run live analysis: {exc}")
            raise HTTPException(status_code=500, detail=f"Live analysis trigger failed: {exc}")

    # Semantic search in uploaded documents
    context = ""
    rag_found = False
    try:
        results = vector_store.search(last_user_message)
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            if docs:
                context = "\n\n".join([f"[Retrieved Document Context]:\n{doc}" for doc in docs])
                if len(docs) > 0 and any(doc.strip() for doc in docs):
                    rag_found = True
    except Exception as e:
        app_logger.warning(f"[Chat Endpoint] RAG Vector store search failed: {e}")

    # Retrieve database history context
    db_context = ""
    company_names_in_db = set()
    try:
        from models.analysis import Analysis
        from sqlalchemy import select
        from database.session import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            db_res = await session.execute(
                select(Analysis).order_by(Analysis.created_at.desc()).limit(10)
            )
            analyses = db_res.scalars().all()
            if analyses:
                db_context = "\nHISTORICAL STARTUP EVALUATION RECORDS IN DATABASE:\n"
                for item in analyses:
                    company_names_in_db.add(item.company_name.lower().strip())
                    dec = item.final_decision or {}
                    db_context += (
                        f"- Company: {item.company_name} | "
                        f"Score: {dec.get('final_score', 'N/A')} | "
                        f"Verdict: {dec.get('verdict', 'N/A')} | "
                        f"Summary: {dec.get('narrative', 'No narrative provided.')[:300]}...\n"
                    )
    except Exception as e:
        app_logger.warning(f"[Chat Endpoint] Failed to load DB context: {e}")

    # Live search fallback if not in DB or RAG
    live_search_context = ""
    db_company_mentioned = any(co in last_user_message.lower() for co in company_names_in_db)
    if not db_company_mentioned and not rag_found:
        try:
            from tools.search_tool import search_tool
            app_logger.info(f"[Chat Endpoint] Query matches no DB/RAG records. Running live search for '{last_user_message}'...")
            search_results = await search_tool.search(last_user_message)
            if search_results:
                live_search_context = "\nLIVE WEB SEARCH RESULTS:\n"
                for res in search_results:
                    live_search_context += f"- Title: {res['title']} | URL: {res['url']}\n  Content: {res['content']}\n"
        except Exception as e:
            app_logger.warning(f"[Chat Endpoint] Live search failed: {e}")

    # Build context-rich prompt for the LLM
    prompt = f"""You are 'VentureMind AI Chatbot', an expert Venture Capital Investment Assistant.
You help startup founders and VCs analyze deals, explain startup metrics, answer due diligence questions, and search context from uploaded pitch decks/whitepapers.

Your Tone:
- Professional, analytical, objective, and evidence-driven (like a senior VC investment committee member).
- Direct and clear.

{db_context}

{live_search_context}

CONTEXT FROM MEMORIZED PROJECT DOCUMENTS:
{context or "(No relevant specification documents or uploaded pitch decks found matching this query in RAG memory)"}

CONVERSATION HISTORY:
"""
    # Append recent conversation history (max settings.CHAT_HISTORY_MESSAGES messages for context window management)
    history_limit = settings.CHAT_HISTORY_MESSAGES
    history = request.messages[-history_limit:-1] if len(request.messages) > history_limit else request.messages[:-1]
    for msg in history:
        role_label = "USER" if msg.role == "user" else "ASSISTANT"
        prompt += f"{role_label}: {msg.content}\n"
    
    prompt += f"USER: {last_user_message}\n"
    prompt += "ASSISTANT:"

    try:
        response_text = await llm_service.generate_chat(prompt)
        return {
            "content": response_text
        }
    except AllLLMProvidersFailedError as exc:
        app_logger.error(f"[Chat Endpoint] AI provider temporarily unavailable: {exc}")
        raise HTTPException(status_code=503, detail="AI provider temporarily unavailable, please retry.")
    except Exception as exc:
        app_logger.error(f"[Chat Endpoint] Failed to generate LLM response: {exc}")
        raise HTTPException(status_code=500, detail="LLM generation failed. Check API key configurations.")
