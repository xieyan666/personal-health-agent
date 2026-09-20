"""User data access."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from backend.app.models import User
from backend.app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_external_identity(
        self, auth_source: str, external_user_id: str
    ) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(
                User.auth_source == auth_source,
                User.external_user_id == external_user_id,
            )
        )
        return result.scalar_one_or_none()
