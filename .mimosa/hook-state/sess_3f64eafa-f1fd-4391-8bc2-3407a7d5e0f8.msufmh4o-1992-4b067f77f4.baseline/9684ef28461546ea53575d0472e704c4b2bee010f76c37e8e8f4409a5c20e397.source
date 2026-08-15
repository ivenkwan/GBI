"""Conversation endpoints — multi-turn chat history (Phase 14)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_user

router = APIRouter()


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]
    count: int


class MessageOut(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str
    generated_sql: str | None = None
    created_at: str


class MessageListResponse(BaseModel):
    messages: list[MessageOut]
    count: int


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    user: dict = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List the current user's conversations, most recently active first."""
    from app.services import conversations as conversations_service

    try:
        rows = await conversations_service.list_conversations(
            user_id=user["sub"], tenant_id=user["tenant_id"], limit=limit
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PERSISTENCE_UNAVAILABLE",
                "message": f"Conversation store unavailable: {type(e).__name__}",
            },
        ) from None

    return ConversationListResponse(
        conversations=[ConversationSummary(**row) for row in rows], count=len(rows)
    )


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def list_messages(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
):
    """List a conversation's most recent turns (chronological order).

    RLS scopes rows to the caller's tenant; other tenants' conversation ids
    simply return zero messages.
    """
    from app.services import conversations as conversations_service

    try:
        uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_CONVERSATION", "message": "Not a valid conversation id"},
        ) from None

    try:
        rows = await conversations_service.list_messages(
            conversation_id=conversation_id, tenant_id=user["tenant_id"], limit=limit
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PERSISTENCE_UNAVAILABLE",
                "message": f"Conversation store unavailable: {type(e).__name__}",
            },
        ) from None

    return MessageListResponse(messages=[MessageOut(**row) for row in rows], count=len(rows))
