"""Conversation and message data access."""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import select

from backend.app.models import Conversation, Message
from backend.app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    async def list(
        self, offset: int = 0, limit: int = 100
    ) -> List[Conversation]:
        return await self._list(
            select(Conversation).order_by(Conversation.updated_at.desc()),
            offset,
            limit,
        )

    async def list_by_user_id(
        self, user_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[Conversation]:
        return await self._list(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc()),
            offset,
            limit,
        )

    async def list_by_agent_id(
        self, agent_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[Conversation]:
        return await self._list(
            select(Conversation)
            .where(Conversation.agent_id == agent_id)
            .order_by(Conversation.updated_at.desc()),
            offset,
            limit,
        )

    async def list_by_user_and_agent(
        self,
        user_id: UUID,
        agent_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Conversation]:
        return await self._list(
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.agent_id == agent_id,
            )
            .order_by(Conversation.updated_at.desc()),
            offset,
            limit,
        )


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def list(self, offset: int = 0, limit: int = 100) -> List[Message]:
        return await self._list(
            select(Message).order_by(Message.created_at.asc()), offset, limit
        )

    async def list_by_conversation_id(
        self, conversation_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[Message]:
        return await self._list(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc()),
            offset,
            limit,
        )

    async def list_children(
        self, parent_message_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[Message]:
        return await self._list(
            select(Message)
            .where(Message.parent_message_id == parent_message_id)
            .order_by(Message.created_at.asc()),
            offset,
            limit,
        )

    async def exists_by_conversation_id(self, conversation_id: UUID) -> bool:
        result = await self.session.execute(
            select(Message.id)
            .where(Message.conversation_id == conversation_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def exists_children(self, parent_message_id: UUID) -> bool:
        result = await self.session.execute(
            select(Message.id)
            .where(Message.parent_message_id == parent_message_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
