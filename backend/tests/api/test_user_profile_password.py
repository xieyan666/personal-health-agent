"""Integration coverage for the current-user password-change endpoint."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.auth.jwt import create_access_token
from backend.app.auth.security import hash_password, verify_password
from backend.app.core.database import AsyncSessionFactory
from backend.app.models import AuditLog, User


@pytest.mark.asyncio
async def test_current_user_can_change_only_own_password(api_context: tuple) -> None:
    client, track_id = api_context
    user = User(
        id=uuid4(),
        username=f"password_change_{uuid4().hex}",
        display_name="Password Test User",
        auth_source="local",
        password_hash=hash_password("OldPassword1"),
        role="employee",
        status="active",
    )
    async with AsyncSessionFactory() as session:
        session.add(user)
        await session.commit()
    track_id(User, user.id)
    headers = {"Authorization": f"Bearer {create_access_token(user)}"}

    wrong = await client.post(
        "/api/v1/users/me/change-password",
        headers=headers,
        json={"current_password": "WrongPassword1", "new_password": "NewPassword2"},
    )
    assert wrong.status_code == 400
    assert wrong.json()["detail"] == "当前密码不正确"

    response = await client.post(
        "/api/v1/users/me/change-password",
        headers=headers,
        json={"current_password": "OldPassword1", "new_password": "NewPassword2"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    async with AsyncSessionFactory() as session:
        saved = await session.get(User, user.id)
        assert saved is not None
        assert verify_password("NewPassword2", saved.password_hash)
        assert not verify_password("OldPassword1", saved.password_hash)
        audit = await session.scalar(select(AuditLog).where(AuditLog.actor_user_id == user.id))
        assert audit is not None
        assert audit.action == "password_changed"
        assert audit.details == {}
        track_id(AuditLog, audit.id)
