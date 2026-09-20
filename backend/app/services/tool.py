"""Tool registry business operations."""

from __future__ import annotations

from typing import Any, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import Tool
from backend.app.repositories import ToolRepository
from backend.app.services.base import BaseService
from backend.app.services.exceptions import ConflictError, NotFoundError


class ToolService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repository = ToolRepository(session)

    async def get_tool(self, tool_id: UUID) -> Tool:
        tool = await self.repository.get_by_id(tool_id)
        if tool is None:
            raise NotFoundError(f"Tool not found: {tool_id}")
        return tool

    async def list_tools(self, offset: int = 0, limit: int = 100) -> List[Tool]:
        return await self.repository.list(offset, limit)

    async def create_tool(self, **values: Any) -> Tool:
        async with self._transaction():
            if await self.repository.get_by_name(values["name"]):
                raise ConflictError(f"Tool name already exists: {values['name']}")
            if await self.repository.get_by_implementation_ref(values["implementation_ref"]):
                raise ConflictError("Tool implementation_ref already exists")
            return await self.repository.create(**values)

    async def update_tool(self, tool_id: UUID, **values: Any) -> Tool:
        async with self._transaction():
            tool = await self.get_tool(tool_id)
            return await self.repository.update(tool, **values)

    async def delete_tool(self, tool_id: UUID) -> None:
        async with self._transaction():
            await self.repository.delete(await self.get_tool(tool_id))
