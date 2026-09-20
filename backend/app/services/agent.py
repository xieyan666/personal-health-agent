"""Agent definition business operations."""

from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import Agent
from backend.app.repositories import AgentRepository, ModelConfigRepository, UserRepository
from backend.app.services.base import BaseService
from backend.app.services.exceptions import ConflictError, NotFoundError, ValidationError


class AgentService(BaseService):
    VALID_SCOPES = {"system", "personal"}

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repository = AgentRepository(session)
        self.users = UserRepository(session)
        self.model_configs = ModelConfigRepository(session)

    async def get_agent(self, agent_id: UUID) -> Agent:
        agent = await self.repository.get_by_id(agent_id)
        if agent is None:
            raise NotFoundError(f"Agent not found: {agent_id}")
        return agent

    async def list_agents(
        self,
        offset: int = 0,
        limit: int = 100,
        scope: Optional[str] = None,
        owner_user_id: Optional[UUID] = None,
    ) -> List[Agent]:
        if owner_user_id is not None:
            return await self.repository.list_by_owner_user_id(
                owner_user_id, offset, limit
            )
        if scope == "system":
            return await self.repository.list_system_agents(offset, limit)
        if scope == "personal":
            return await self.repository.list_personal_agents(offset, limit)
        return await self.repository.list(offset, limit)

    async def create_agent(self, **values: Any) -> Agent:
        async with self._transaction():
            if await self.repository.get_by_code(values["code"]):
                raise ConflictError(f"Agent code already exists: {values['code']}")
            scope = values.get("scope")
            owner_id = values.get("owner_user_id")
            await self._validate_scope_and_owner(scope, owner_id)
            model_config_id = values.get("model_config_id")
            if model_config_id is not None and await self.model_configs.get_by_id(model_config_id) is None:
                raise NotFoundError(f"Model config not found: {model_config_id}")
            return await self.repository.create(**values)

    async def update_agent(self, agent_id: UUID, **values: Any) -> Agent:
        async with self._transaction():
            agent = await self.get_agent(agent_id)
            code = values.get("code")
            if code is not None and code != agent.code:
                existing = await self.repository.get_by_code(code)
                if existing is not None:
                    raise ConflictError(f"Agent code already exists: {code}")
            final_scope = values.get("scope", agent.scope)
            final_owner_id = values.get("owner_user_id", agent.owner_user_id)
            await self._validate_scope_and_owner(final_scope, final_owner_id)
            model_config_id = values.get("model_config_id", agent.model_config_id)
            if (
                model_config_id is not None
                and await self.model_configs.get_by_id(model_config_id) is None
            ):
                raise NotFoundError(f"Model config not found: {model_config_id}")
            updated = await self.repository.update(agent, **values)
        await self.session.refresh(updated)
        return updated

    async def delete_agent(self, agent_id: UUID) -> None:
        async with self._transaction():
            await self.repository.delete(await self.get_agent(agent_id))

    async def _validate_scope_and_owner(
        self, scope: Any, owner_user_id: Any
    ) -> None:
        if scope not in self.VALID_SCOPES:
            raise ValidationError(f"Invalid agent scope: {scope}")
        if scope == "personal" and owner_user_id is None:
            raise ValidationError("Personal agent requires owner_user_id")
        if owner_user_id is not None and await self.users.get_by_id(owner_user_id) is None:
            raise NotFoundError(f"Owner user not found: {owner_user_id}")
