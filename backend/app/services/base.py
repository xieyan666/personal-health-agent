"""Shared Service transaction boundary."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession


class BaseService:
    """Own commits and rollbacks for an externally supplied AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[None]:
        try:
            yield
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
