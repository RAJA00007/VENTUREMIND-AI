from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from langchain_core.messages import HumanMessage

from workflows.chat_workflow import chatbot, stream_generator
from core.security import get_current_user
from models.user import User

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
def chat_stream_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    user_msg = request.message
    if not user_msg and request.messages:
        user_msg = request.messages[-1].get("content", "")
    
    if not user_msg:
        raise HTTPException(status_code=400, detail="No message content provided.")
    
    thread_id = request.thread_id or "default_thread"
    scoped_thread_id = f"user_{current_user.id}_{thread_id}"

    return StreamingResponse(
        stream_generator(user_msg, scoped_thread_id),
        media_type="text/event-stream"
    )

@router.post("")
def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    user_msg = request.message
    if not user_msg and request.messages:
        user_msg = request.messages[-1].get("content", "")
    
    if not user_msg:
        raise HTTPException(status_code=400, detail="No message content provided.")
    
    thread_id = request.thread_id or "default_thread"
    scoped_thread_id = f"user_{current_user.id}_{thread_id}"

    if request.stream:
        return StreamingResponse(
            stream_generator(user_msg, scoped_thread_id),
            media_type="text/event-stream"
        )

    chunks = list(stream_generator(user_msg, scoped_thread_id))
    full_response = "".join(chunks)
    return {
        "response": full_response,
        "content": full_response,
        "detail": full_response,
        "thread_id": thread_id
    }

@router.get("/history/{thread_id}")
def get_history(
    thread_id: str,
    current_user: User = Depends(get_current_user)
):
    scoped_thread_id = f"user_{current_user.id}_{thread_id}"
    config = {"configurable": {"thread_id": scoped_thread_id}}
    state = chatbot.get_state(config)
    messages = state.values.get("messages", [])
    history = []
    for msg in messages:
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        history.append({"role": role, "content": msg.content})
    return {"history": history}

