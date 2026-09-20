"""Append-only audit business operations."""

from __future__ import annotations

from typing import Any, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import AuditLog
from backend.app.repositories import AgentRunRepository, AuditLogRepository, UserRepository
from backend.app.services.base import BaseService
from backend.app.services.exceptions import NotFoundError


class AuditLogService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repository = AuditLogRepository(session)
        self.users = UserRepository(session)
        self.runs = AgentRunRepository(session)

    async def get_audit_log(self, audit_id: UUID) -> AuditLog:
        audit = await self.repository.get_by_id(audit_id)
        if audit is None:
            raise NotFoundError(f"Audit log not found: {audit_id}")
        return audit

    async def list_audit_logs(self, offset: int = 0, limit: int = 100) -> List[AuditLog]:
        return await self.repository.list(offset, limit)

    async def create_audit_log(self, **values: Any) -> AuditLog:
        async with self._transaction():
            actor_id = values.get("actor_user_id")
            if actor_id is not None and await self.users.get_by_id(actor_id) is None:
                raise NotFoundError(f"Actor user not found: {actor_id}")
            run_id = values.get("agent_run_id")
            if run_id is not None and await self.runs.get_by_id(run_id) is None:
                raise NotFoundError(f"Agent run not found: {run_id}")
            return await self.repository.create(**values)
