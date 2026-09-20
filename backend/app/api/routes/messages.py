"""Message persistence endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from backend.app.api.deps import get_message_service
from backend.app.auth.jwt import get_optional_current_user
from backend.app.api.deps import get_conversation_service
from backend.app.schemas import MessageCreate, MessageResponse
from backend.app.services import MessageService


router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    payload: MessageCreate,
    service: MessageService = Depends(get_message_service),
) -> MessageResponse:
    return await service.create_message(**payload.model_dump())


@router.get("", response_model=List[MessageResponse])
async def list_messages(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    conversation_id: Optional[UUID] = Query(default=None),
    parent_message_id: Optional[UUID] = Query(default=None),
    service: MessageService = Depends(get_message_service),
    conversation_service=Depends(get_conversation_service),
    current_user=Depends(get_optional_current_user),
) -> List[MessageResponse]:
    if conversation_id is not None and parent_message_id is not None:
        raise HTTPException(
            status_code=422,
            detail="conversation_id and parent_message_id cannot be combined",
        )
    if conversation_id is not None:
        if current_user is not None:
            conversation = await conversation_service.get_conversation(conversation_id)
            if conversation.user_id != current_user.id:
                raise HTTPException(403, "无权访问其他用户会话")
        return await service.list_messages(conversation_id, offset, limit)
    if parent_message_id is not None:
        return await service.list_children(parent_message_id, offset, limit)
    return await service.list_all_messages(offset, limit)


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: UUID,
    service: MessageService = Depends(get_message_service),
) -> MessageResponse:
    return await service.get_message(message_id)


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: UUID,
    service: MessageService = Depends(get_message_service),
) -> Response:
    await service.delete_message(message_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
