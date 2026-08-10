from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from langchain_core.messages import HumanMessage

from workflows.chat_workflow import chatbot, stream_generator

router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)

class ChatRequest(BaseModel):
    message: Optional[str] = None
    thread_id: Optional[str] = "default_thread"
    messages: Optional[List[dict]] = None
    stream: Optional[bool] = False

@router.post("/stream")
def chat_stream_endpoint(request: ChatRequest):
    user_msg = request.message
    if not user_msg and request.messages:
        user_msg = request.messages[-1].get("content", "")
    
    if not user_msg:
        raise HTTPException(status_code=400, detail="No message content provided.")
    
    thread_id = request.thread_id or "default_thread"

    return StreamingResponse(
        stream_generator(user_msg, thread_id),
        media_type="text/event-stream"
    )

@router.post("")
def chat_endpoint(request: ChatRequest):
    user_msg = request.message
    if not user_msg and request.messages:
        user_msg = request.messages[-1].get("content", "")
    
    if not user_msg:
        raise HTTPException(status_code=400, detail="No message content provided.")
    
    thread_id = request.thread_id or "default_thread"

    if request.stream:
        return StreamingResponse(
            stream_generator(user_msg, thread_id),
            media_type="text/event-stream"
        )

    chunks = list(stream_generator(user_msg, thread_id))
    full_response = "".join(chunks)
    return {
        "response": full_response,
        "content": full_response,
        "detail": full_response,
        "thread_id": thread_id
    }

@router.get("/history/{thread_id}")
def get_history(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    state = chatbot.get_state(config)
    messages = state.values.get("messages", [])
    history = []
    for msg in messages:
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        history.append({"role": role, "content": msg.content})
    return {"history": history}

