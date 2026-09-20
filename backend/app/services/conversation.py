"""Conversation and message business operations."""

from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import Conversation, Message
from backend.app.repositories import (
    AgentRepository,
    AgentRunRepository,
    ConversationRepository,
    MessageRepository,
    UserRepository,
)
from backend.app.services.base import BaseService
from backend.app.services.exceptions import ConflictError, NotFoundError, ValidationError


class ConversationService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repository = ConversationRepository(session)
        self.users = UserRepository(session)
        self.agents = AgentRepository(session)
        self.messages = MessageRepository(session)
        self.agent_runs = AgentRunRepository(session)

    async def get_conversation(self, conversation_id: UUID) -> Conversation:
        conversation = await self.repository.get_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError(f"Conversation not found: {conversation_id}")
        return conversation

    async def list_user_conversations(self, user_id: UUID, offset: int = 0, limit: int = 100) -> List[Conversation]:
        return await self.repository.list_by_user_id(user_id, offset, limit)

    async def list_conversations(
        self,
        offset: int = 0,
        limit: int = 100,
        user_id: Optional[UUID] = None,
        agent_id: Optional[UUID] = None,
    ) -> List[Conversation]:
        if user_id is not None and agent_id is not None:
            return await self.repository.list_by_user_and_agent(
                user_id, agent_id, offset, limit
            )
        if user_id is not None:
            return await self.repository.list_by_user_id(user_id, offset, limit)
        if agent_id is not None:
            return await self.repository.list_by_agent_id(agent_id, offset, limit)
        return await self.repository.list(offset, limit)

    async def create_conversation(self, **values: Any) -> Conversation:
        async with self._transaction():
            if await self.users.get_by_id(values["user_id"]) is None:
                raise NotFoundError(f"User not found: {values['user_id']}")
            if await self.agents.get_by_id(values["agent_id"]) is None:
                raise NotFoundError(f"Agent not found: {values['agent_id']}")
            return await self.repository.create(**values)

    async def update_conversation(self, conversation_id: UUID, **values: Any) -> Conversation:
        async with self._transaction():
            conversation = await self.get_conversation(conversation_id)
            updated = await self.repository.update(conversation, **values)
        await self.session.refresh(updated)
        return updated

    async def delete_conversation(self, conversation_id: UUID) -> None:
        async with self._transaction():
            conversation = await self.get_conversation(conversation_id)
            if await self.messages.exists_by_conversation_id(conversation_id):
                raise ConflictError("Conversation is referenced by messages")
            if await self.agent_runs.exists_by_conversation_id(conversation_id):
                raise ConflictError("Conversation is referenced by agent runs")
            await self.repository.delete(conversation)


class MessageService(BaseService):
    VALID_ROLES = {"user", "assistant", "system", "tool"}

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repository = MessageRepository(session)
        self.conversations = ConversationRepository(session)
        self.agent_runs = AgentRunRepository(session)

    async def get_message(self, message_id: UUID) -> Message:
        message = await self.repository.get_by_id(message_id)
        if message is None:
            raise NotFoundError(f"Message not found: {message_id}")
        return message

    async def list_messages(self, conversation_id: UUID, offset: int = 0, limit: int = 100) -> List[Message]:
        return await self.repository.list_by_conversation_id(conversation_id, offset, limit)

    async def list_all_messages(
        self, offset: int = 0, limit: int = 100
    ) -> List[Message]:
        return await self.repository.list(offset, limit)

    async def list_children(
        self, parent_message_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[Message]:
        return await self.repository.list_children(parent_message_id, offset, limit)

    async def create_message(self, **values: Any) -> Message:
        async with self._transaction():
            role = values.get("role")
            if role not in self.VALID_ROLES:
                raise ValidationError(f"Invalid message role: {role}")
            conversation_id = values["conversation_id"]
            if await self.conversations.get_by_id(conversation_id) is None:
                raise NotFoundError(f"Conversation not found: {conversation_id}")
            parent_id = values.get("parent_message_id")
            if parent_id is not None:
                parent = await self.repository.get_by_id(parent_id)
                if parent is None:
                    raise NotFoundError(f"Parent message not found: {parent_id}")
                if parent.conversation_id != conversation_id:
                    raise ValidationError("Parent message belongs to another conversation")
            return await self.repository.create(**values)

    async def delete_message(self, message_id: UUID) -> None:
        async with self._transaction():
            message = await self.get_message(message_id)
            if await self.repository.exists_children(message_id):
                raise ConflictError("Message is referenced by child messages")
            if await self.agent_runs.exists_by_message_id(message_id):
                raise ConflictError("Message is referenced by agent runs")
            await self.repository.delete(message)
