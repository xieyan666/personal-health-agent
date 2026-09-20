"""Agent definition data access."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select

from backend.app.models import Agent
from backend.app.repositories.base import BaseRepository


class AgentRepository(BaseRepository[Agent]):
    model = Agent

    async def get_by_code(self, code: str) -> Optional[Agent]:
        result = await self.session.execute(select(Agent).where(Agent.code == code))
        return result.scalar_one_or_none()

    async def exists_by_model_config_id(self, model_config_id: UUID) -> bool:
        result = await self.session.execute(
            select(Agent.id)
            .where(Agent.model_config_id == model_config_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_by_owner_user_id(
        self, owner_user_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[Agent]:
        return await self._list(
            select(Agent).where(Agent.owner_user_id == owner_user_id), offset, limit
        )

    async def list_system_agents(
        self, offset: int = 0, limit: int = 100
    ) -> List[Agent]:
        return await self._list(
            select(Agent).where(Agent.scope == "system"), offset, limit
        )

    async def list_personal_agents(
        self, offset: int = 0, limit: int = 100
    ) -> List[Agent]:
        return await self._list(
            select(Agent).where(Agent.scope == "personal"), offset, limit
        )
