"""Tool registry data access."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from backend.app.models import Tool
from backend.app.repositories.base import BaseRepository


class ToolRepository(BaseRepository[Tool]):
    model = Tool

    async def get_by_name(self, name: str) -> Optional[Tool]:
        result = await self.session.execute(select(Tool).where(Tool.name == name))
        return result.scalar_one_or_none()

    async def get_by_implementation_ref(
        self, implementation_ref: str
    ) -> Optional[Tool]:
        result = await self.session.execute(
            select(Tool).where(Tool.implementation_ref == implementation_ref)
        )
        return result.scalar_one_or_none()
