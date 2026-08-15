"""Chat endpoint — natural language to SQL + chart + narrative pipeline."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.models.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter()


class FeedbackRequest(BaseModel):
    """Thumbs up/down on a chat response (updates audit_log.feedback_score)."""

    session_id: str = Field(min_length=36, max_length=36)
    score: int = Field(ge=-1, le=1, description="1 = up, -1 = down, 0 = clear")


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
):
    """Main chat endpoint. Accepts a natural language query and returns
    SQL, chart spec, and narrative insight in a streaming or single response."""
    service = ChatService(tenant_id=user["tenant_id"])
    return await service.process_query(
        query=request.query,
        user_id=user["sub"],
        roles=user.get("roles", []),
        conversation_id=request.conversation_id,
        confirm_large_query=request.confirm_large_query,
    )


@router.post("/feedback")
async def chat_feedback(
    request: FeedbackRequest,
    user: dict = Depends(get_current_user),
):
    """Record thumbs-up/down feedback on a chat response.

    The score lands on the audit rows of the session (the SSE start event
    / sync response session id — NOT the conversation id).
    """
    from app.services.audit import record_feedback

    ok = await record_feedback(
        session_id=request.session_id,
        tenant_id=user["tenant_id"],
        score=request.score,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "FEEDBACK_UNAVAILABLE",
                "message": "Could not record feedback (no matching audit rows "
                "or the audit store is unreachable)",
            },
        )
    return {"status": "recorded", "session_id": request.session_id, "score": request.score}


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
):
    """Streaming variant — yields SSE events as the agent pipeline progresses."""
    from fastapi.responses import StreamingResponse

    service = ChatService(tenant_id=user["tenant_id"])
    return StreamingResponse(
        service.process_query_stream(
            query=request.query,
            user_id=user["sub"],
            roles=user.get("roles", []),
            conversation_id=request.conversation_id,
            confirm_large_query=request.confirm_large_query,
        ),
        media_type="text/event-stream",
    )
