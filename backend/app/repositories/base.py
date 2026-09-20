"""Generic asynchronous SQLAlchemy repository primitives."""

from __future__ import annotations

from typing import Any, Generic, List, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from backend.app.models.base import Base


ModelT = TypeVar("ModelT", bound=Base)


def validate_pagination(offset: int, limit: int) -> None:
    """Validate the Repository-wide offset/limit contract."""
    if offset < 0:
        raise ValueError("offset must be greater than or equal to 0")
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")


class BaseRepository(Generic[ModelT]):
    """Lightweight CRUD repository using an externally owned AsyncSession."""

    model: Type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, object_id: UUID) -> Optional[ModelT]:
        return await self.session.get(self.model, object_id)

    async def list(self, offset: int = 0, limit: int = 100) -> List[ModelT]:
        return await self._list(select(self.model), offset, limit)

    async def create(self, **values: Any) -> ModelT:
        instance = self.model(**values)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, instance: ModelT, **values: Any) -> ModelT:
        mapper = inspect(type(instance))
        primary_keys = {column.key for column in mapper.primary_key}
        writable_columns = {attribute.key for attribute in mapper.column_attrs}
        for key, value in values.items():
            if key in primary_keys:
                raise ValueError(f"primary key cannot be updated: {key}")
            if key not in writable_columns:
                raise ValueError(f"unknown or internal model attribute: {key}")
            setattr(instance, key, value)
        await self.session.flush()
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self.session.delete(instance)
        await self.session.flush()

    async def _list(
        self,
        statement: Select[Any],
        offset: int = 0,
        limit: int = 100,
    ) -> List[ModelT]:
        validate_pagination(offset, limit)
        result = await self.session.execute(statement.offset(offset).limit(limit))
        return list(result.scalars().all())
