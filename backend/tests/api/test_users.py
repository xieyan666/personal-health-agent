"""Real PostgreSQL integration tests for User API."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.app.models import User


def user_payload(**overrides: object) -> dict:
    token = uuid4().hex
    values = {
        "username": f"api_user_{token}",
        "display_name": "API User",
        "email": f"{token}@example.test",
        "auth_source": "local",
        "status": "active",
        "timezone": "Asia/Shanghai",
    }
    values.update(overrides)
    return values


@pytest.mark.asyncio
async def test_user_crud_errors_and_password_exclusion(api_context: tuple) -> None:
    client, track_id = api_context
    payload = user_payload()

    created = await client.post("/api/v1/users", json=payload)
    assert created.status_code == 201
    body = created.json()
    user_id = UUID(body["id"])
    track_id(User, user_id)
    assert "password_hash" not in body

    fetched = await client.get(f"/api/v1/users/{user_id}")
    assert fetched.status_code == 200
    assert fetched.json()["username"] == payload["username"]
    assert "password_hash" not in fetched.json()

    listed = await client.get("/api/v1/users", params={"offset": 0, "limit": 2})
    assert listed.status_code == 200
    assert len(listed.json()) <= 2
    assert all("password_hash" not in item for item in listed.json())

    updated = await client.patch(
        f"/api/v1/users/{user_id}", json={"display_name": "Updated API User"}
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Updated API User"
    assert updated.json()["timezone"] == payload["timezone"]

    duplicate = await client.post("/api/v1/users", json=user_payload(username=payload["username"]))
    assert duplicate.status_code == 409
    assert "detail" in duplicate.json()

    missing = await client.get(f"/api/v1/users/{uuid4()}")
    assert missing.status_code == 404
    assert (await client.get("/api/v1/users/not-a-uuid")).status_code == 422
    invalid = await client.post("/api/v1/users", json={"display_name": "Missing fields"})
    assert invalid.status_code == 422
    create_with_hash = user_payload(password_hash="client-supplied-hash")
    assert (await client.post("/api/v1/users", json=create_with_hash)).status_code == 422
    assert (await client.patch(
        f"/api/v1/users/{user_id}",
        json={"password_hash": "client-supplied-hash"},
    )).status_code == 422

    deleted = await client.delete(f"/api/v1/users/{user_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert (await client.get(f"/api/v1/users/{user_id}")).status_code == 404


@pytest.mark.asyncio
async def test_user_pagination_validation_and_limit(api_context: tuple) -> None:
    client, track_id = api_context
    for _ in range(3):
        response = await client.post("/api/v1/users", json=user_payload())
        assert response.status_code == 201
        track_id(User, UUID(response.json()["id"]))

    response = await client.get("/api/v1/users?offset=0&limit=2")
    assert response.status_code == 200
    assert len(response.json()) == 2
    for query in ("limit=0", "limit=101", "offset=-1"):
        assert (await client.get(f"/api/v1/users?{query}")).status_code == 422
