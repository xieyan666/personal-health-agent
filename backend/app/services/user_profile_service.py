"""Personal-center profile operations for the current JWT user."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.exceptions import NotFoundError
from backend.app.models import User
from backend.app.schemas.user_profile import UserProfileUpdate


async def get_user_profile(session: AsyncSession, user_id: UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError("用户不存在")
    return user


async def update_user_profile(session: AsyncSession, user_id: UUID, payload: UserProfileUpdate) -> User:
    """Apply only the whitelisted editable fields (schema-level protection)."""
    user = await get_user_profile(session, user_id)
    editable = payload.editable_fields
    if not editable:
        return user
    for key, value in editable.items():
        if hasattr(user, key):
            setattr(user, key, value)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user_avatar(session: AsyncSession, user_id: UUID, object_key: str) -> User:
    """Persist the private MinIO object key, never a public presigned URL."""
    user = await get_user_profile(session, user_id)
    user.avatar_url = object_key
    await session.commit()
    await session.refresh(user)
    return user
