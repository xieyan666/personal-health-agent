"""Append-only audit log data access."""

from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import AuditLog
from backend.app.repositories.base import validate_pagination


class AuditLogRepository:
    """Audit access intentionally exposing no update or delete methods."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, object_id: UUID) -> Optional[AuditLog]:
        return await self.session.get(AuditLog, object_id)

    async def list(self, offset: int = 0, limit: int = 100) -> List[AuditLog]:
        return await self._list(select(AuditLog), offset, limit)

    async def list_by_user_id(
        self, actor_user_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[AuditLog]:
        return await self._list(
            select(AuditLog).where(AuditLog.actor_user_id == actor_user_id),
            offset,
            limit,
        )

    async def list_by_agent_run_id(
        self, agent_run_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[AuditLog]:
        return await self._list(
            select(AuditLog).where(AuditLog.agent_run_id == agent_run_id),
            offset,
            limit,
        )

    async def exists_by_agent_run_id(self, agent_run_id: UUID) -> bool:
        result = await self.session.execute(
            select(AuditLog.id)
            .where(AuditLog.agent_run_id == agent_run_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def create(self, **values: Any) -> AuditLog:
        instance = AuditLog(**values)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def _list(
        self, statement: Any, offset: int, limit: int
    ) -> List[AuditLog]:
        validate_pagination(offset, limit)
        result = await self.session.execute(statement.offset(offset).limit(limit))
        return list(result.scalars().all())
