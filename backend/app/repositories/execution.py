"""Agent run data access."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select

from backend.app.models import AgentRun
from backend.app.repositories.base import BaseRepository


class AgentRunRepository(BaseRepository[AgentRun]):
    model = AgentRun

    async def list(self, offset: int = 0, limit: int = 100) -> List[AgentRun]:
        return await self._list(
            select(AgentRun).order_by(AgentRun.created_at.desc()), offset, limit
        )

    async def list_filtered(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        agent_id: Optional[UUID] = None,
        conversation_id: Optional[UUID] = None,
        parent_run_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> List[AgentRun]:
        statement = select(AgentRun)
        if agent_id is not None:
            statement = statement.where(AgentRun.agent_id == agent_id)
        if conversation_id is not None:
            statement = statement.where(AgentRun.conversation_id == conversation_id)
        if parent_run_id is not None:
            statement = statement.where(AgentRun.parent_run_id == parent_run_id)
        if status is not None:
            statement = statement.where(AgentRun.status == status)
        return await self._list(
            statement.order_by(AgentRun.created_at.desc()), offset, limit
        )

    async def list_by_agent_id(
        self, agent_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[AgentRun]:
        return await self._list(
            select(AgentRun)
            .where(AgentRun.agent_id == agent_id)
            .order_by(AgentRun.created_at.desc()),
            offset,
            limit,
        )

    async def list_by_conversation_id(
        self, conversation_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[AgentRun]:
        return await self._list(
            select(AgentRun)
            .where(AgentRun.conversation_id == conversation_id)
            .order_by(AgentRun.created_at.desc()),
            offset,
            limit,
        )

    async def list_by_parent_run_id(
        self, parent_run_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[AgentRun]:
        return await self._list(
            select(AgentRun)
            .where(AgentRun.parent_run_id == parent_run_id)
            .order_by(AgentRun.created_at.desc()),
            offset,
            limit,
        )

    async def exists_by_conversation_id(self, conversation_id: UUID) -> bool:
        result = await self.session.execute(
            select(AgentRun.id)
            .where(AgentRun.conversation_id == conversation_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def exists_by_message_id(self, message_id: UUID) -> bool:
        result = await self.session.execute(
            select(AgentRun.id)
            .where(
                (AgentRun.trigger_message_id == message_id)
                | (AgentRun.output_message_id == message_id)
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def exists_children(self, run_id: UUID) -> bool:
        result = await self.session.execute(
            select(AgentRun.id).where(AgentRun.parent_run_id == run_id).limit(1)
        )
        return result.scalar_one_or_none() is not None
