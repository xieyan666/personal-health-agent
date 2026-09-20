"""User business operations."""

from __future__ import annotations

from typing import Any, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import User
from backend.app.repositories import UserRepository
from backend.app.services.base import BaseService
from backend.app.services.exceptions import ConflictError, NotFoundError


class UserService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repository = UserRepository(session)

    async def get_user(self, user_id: UUID) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User not found: {user_id}")
        return user

    async def list_users(self, offset: int = 0, limit: int = 100) -> List[User]:
        return await self.repository.list(offset, limit)

    async def create_user(self, **values: Any) -> User:
        async with self._transaction():
            if await self.repository.get_by_username(values["username"]):
                raise ConflictError(f"Username already exists: {values['username']}")
            auth_source = values.get("auth_source")
            external_user_id = values.get("external_user_id")
            if auth_source and external_user_id and await self.repository.get_by_external_identity(
                auth_source, external_user_id
            ):
                raise ConflictError("External identity already exists")
            return await self.repository.create(**values)

    async def update_user(self, user_id: UUID, **values: Any) -> User:
        async with self._transaction():
            user = await self.get_user(user_id)
            updated = await self.repository.update(user, **values)
        await self.session.refresh(updated)
        return updated

    async def delete_user(self, user_id: UUID) -> None:
        async with self._transaction():
            user = await self.get_user(user_id)
            await self.repository.delete(user)
