"""Model provider and model configuration data access."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select

from backend.app.models import ModelConfig, ModelProvider
from backend.app.repositories.base import BaseRepository


class ModelProviderRepository(BaseRepository[ModelProvider]):
    model = ModelProvider

    async def get_by_name(self, name: str) -> Optional[ModelProvider]:
        result = await self.session.execute(
            select(ModelProvider).where(ModelProvider.name == name)
        )
        return result.scalar_one_or_none()


class ModelConfigRepository(BaseRepository[ModelConfig]):
    model = ModelConfig

    async def get_by_name(self, name: str) -> Optional[ModelConfig]:
        result = await self.session.execute(
            select(ModelConfig).where(ModelConfig.name == name)
        )
        return result.scalar_one_or_none()

    async def list_by_provider_id(
        self, provider_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[ModelConfig]:
        return await self._list(
            select(ModelConfig).where(ModelConfig.provider_id == provider_id),
            offset,
            limit,
        )

    async def exists_by_provider_id(self, provider_id: UUID) -> bool:
        result = await self.session.execute(
            select(ModelConfig.id)
            .where(ModelConfig.provider_id == provider_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
