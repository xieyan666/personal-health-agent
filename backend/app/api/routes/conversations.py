"""Conversation CRUD endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status, HTTPException
from backend.app.auth.jwt import get_optional_current_user

from backend.app.api.deps import get_conversation_service
from backend.app.schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
)
from backend.app.services import ConversationService


router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    service: ConversationService = Depends(get_conversation_service),
    current_user=Depends(get_optional_current_user),
) -> ConversationResponse:
    values = payload.model_dump()
    if current_user is not None:
        values["user_id"] = current_user.id
        if values.get("agent_id") is None:
            agents = await service.agents.list_system_agents(0, 1)
            if not agents:
                raise HTTPException(503, "健康助手尚未配置")
            values["agent_id"] = agents[0].id
    if values.get("user_id") is None or values.get("agent_id") is None:
        raise HTTPException(422, "user_id and agent_id are required")
    return await service.create_conversation(**values)


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    user_id: Optional[UUID] = Query(default=None),
    agent_id: Optional[UUID] = Query(default=None),
    service: ConversationService = Depends(get_conversation_service),
    current_user=Depends(get_optional_current_user),
) -> List[ConversationResponse]:
    if current_user is not None:
        if user_id is not None and user_id != current_user.id:
            raise HTTPException(403, "无权访问其他用户会话")
        user_id = current_user.id
    return await service.list_conversations(
        offset, limit, user_id, agent_id
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    service: ConversationService = Depends(get_conversation_service),
    current_user=Depends(get_optional_current_user),
) -> ConversationResponse:
    conversation = await service.get_conversation(conversation_id)
    if current_user is not None and conversation.user_id != current_user.id:
        raise HTTPException(403, "无权访问其他用户会话")
    return conversation


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    service: ConversationService = Depends(get_conversation_service),
    current_user=Depends(get_optional_current_user),
) -> ConversationResponse:
    conversation = await service.get_conversation(conversation_id)
    if current_user is not None and conversation.user_id != current_user.id:
        raise HTTPException(403, "无权访问其他用户会话")
    return await service.update_conversation(
        conversation_id, **payload.model_dump(exclude_unset=True)
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    service: ConversationService = Depends(get_conversation_service),
    current_user=Depends(get_optional_current_user),
) -> Response:
    conversation = await service.get_conversation(conversation_id)
    if current_user is not None and conversation.user_id != current_user.id:
        raise HTTPException(403, "无权访问其他用户会话")
    await service.delete_conversation(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
