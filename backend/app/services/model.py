"""Model provider and configuration business operations."""

from __future__ import annotations

from typing import Any, List, Mapping, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.model_gateway.chat import normalize_chat_parameters
from backend.app.models import ModelConfig, ModelProvider
from backend.app.repositories import (
    AgentRepository,
    ModelConfigRepository,
    ModelProviderRepository,
)
from backend.app.services.base import BaseService
from backend.app.services.exceptions import ConflictError, NotFoundError


class ModelProviderService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repository = ModelProviderRepository(session)
        self.model_configs = ModelConfigRepository(session)

    async def get_provider(self, provider_id: UUID) -> ModelProvider:
        provider = await self.repository.get_by_id(provider_id)
        if provider is None:
            raise NotFoundError(f"Model provider not found: {provider_id}")
        return provider

    async def list_providers(self, offset: int = 0, limit: int = 100) -> List[ModelProvider]:
        return await self.repository.list(offset, limit)

    async def create_provider(self, **values: Any) -> ModelProvider:
        async with self._transaction():
            if await self.repository.get_by_name(values["name"]):
                raise ConflictError(f"Provider name already exists: {values['name']}")
            return await self.repository.create(**values)

    async def update_provider(self, provider_id: UUID, **values: Any) -> ModelProvider:
        async with self._transaction():
            provider = await self.get_provider(provider_id)
            name = values.get("name")
            if name is not None and name != provider.name:
                existing = await self.repository.get_by_name(name)
                if existing is not None:
                    raise ConflictError(f"Provider name already exists: {name}")
            updated = await self.repository.update(provider, **values)
        await self.session.refresh(updated)
        return updated

    async def delete_provider(self, provider_id: UUID) -> None:
        async with self._transaction():
            provider = await self.get_provider(provider_id)
            if await self.model_configs.exists_by_provider_id(provider_id):
                raise ConflictError("Model provider is referenced by model configs")
            await self.repository.delete(provider)


class ModelConfigService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repository = ModelConfigRepository(session)
        self.providers = ModelProviderRepository(session)
        self.agents = AgentRepository(session)

    async def get_model_config(self, config_id: UUID) -> ModelConfig:
        config = await self.repository.get_by_id(config_id)
        if config is None:
            raise NotFoundError(f"Model config not found: {config_id}")
        return config

    async def list_model_configs(
        self,
        offset: int = 0,
        limit: int = 100,
        provider_id: Optional[UUID] = None,
    ) -> List[ModelConfig]:
        if provider_id is not None:
            return await self.repository.list_by_provider_id(
                provider_id, offset, limit
            )
        return await self.repository.list(offset, limit)

    async def create_model_config(self, **values: Any) -> ModelConfig:
        if values.get("model_type") == "chat":
            parameters = values.get("parameters", {})
            if not isinstance(parameters, Mapping):
                normalize_chat_parameters(parameters)
            if "max_tokens" in parameters:
                normalize_chat_parameters(parameters)
            values["parameters"] = dict(parameters)
        async with self._transaction():
            if await self.providers.get_by_id(values["provider_id"]) is None:
                raise NotFoundError(f"Model provider not found: {values['provider_id']}")
            if await self.repository.get_by_name(values["name"]):
                raise ConflictError(f"Model config name already exists: {values['name']}")
            return await self.repository.create(**values)

    async def update_model_config(self, config_id: UUID, **values: Any) -> ModelConfig:
        async with self._transaction():
            config = await self.get_model_config(config_id)
            name = values.get("name")
            if name is not None and name != config.name:
                existing = await self.repository.get_by_name(name)
                if existing is not None:
                    raise ConflictError(f"Model config name already exists: {name}")
            provider_id = values.get("provider_id", config.provider_id)
            if await self.providers.get_by_id(provider_id) is None:
                raise NotFoundError(f"Model provider not found: {provider_id}")
            if values.get("model_type", config.model_type) == "chat" and "parameters" in values:
                parameters = values["parameters"]
                if not isinstance(parameters, Mapping):
                    normalize_chat_parameters(parameters)
                if "max_tokens" in parameters:
                    normalize_chat_parameters(parameters)
                values["parameters"] = dict(parameters)
            updated = await self.repository.update(config, **values)
        await self.session.refresh(updated)
        return updated

    async def delete_model_config(self, config_id: UUID) -> None:
        async with self._transaction():
            config = await self.get_model_config(config_id)
            if await self.agents.exists_by_model_config_id(config_id):
                raise ConflictError("Model config is referenced by agents")
            await self.repository.delete(config)
