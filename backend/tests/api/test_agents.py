"""Real PostgreSQL integration tests for Agent API."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.app.models import Agent, User


def user_payload() -> dict:
    token = uuid4().hex
    return {
        "username": f"agent_owner_{token}",
        "display_name": "Agent Owner",
        "email": f"{token}@example.test",
        "auth_source": "local",
        "status": "active",
        "timezone": "Asia/Shanghai",
    }


def agent_payload(**overrides: object) -> dict:
    values = {
        "code": f"api_agent_{uuid4().hex}",
        "name": "API Agent",
        "description": "API integration agent",
        "scope": "system",
        "owner_user_id": None,
        "category": "daily_health",
        "status": "active",
        "config": {},
        "version": 1,
    }
    values.update(overrides)
    return values


@pytest.mark.asyncio
async def test_agent_combined_scope_and_owner_filter_is_rejected(
    api_context: tuple,
) -> None:
    client, _ = api_context
    response = await client.get(
        "/api/v1/agents",
        params={"scope": "personal", "owner_user_id": str(uuid4())},
    )
    assert response.status_code == 422
    assert response.json() == {
        "detail": "scope and owner_user_id cannot be combined"
    }


@pytest.mark.asyncio
async def test_agent_crud_filters_and_error_mapping(api_context: tuple) -> None:
    client, track_id = api_context
    owner_response = await client.post("/api/v1/users", json=user_payload())
    assert owner_response.status_code == 201
    owner_id = UUID(owner_response.json()["id"])
    track_id(User, owner_id)

    system_payload = agent_payload()
    created = await client.post("/api/v1/agents", json=system_payload)
    assert created.status_code == 201
    system_id = UUID(created.json()["id"])
    track_id(Agent, system_id)

    personal = await client.post(
        "/api/v1/agents",
        json=agent_payload(scope="personal", owner_user_id=str(owner_id)),
    )
    assert personal.status_code == 201
    personal_id = UUID(personal.json()["id"])
    track_id(Agent, personal_id)

    fetched = await client.get(f"/api/v1/agents/{system_id}")
    assert fetched.status_code == 200
    assert fetched.json()["code"] == system_payload["code"]

    listed = await client.get("/api/v1/agents?offset=0&limit=2")
    assert listed.status_code == 200
    assert len(listed.json()) == 2
    system_list = await client.get("/api/v1/agents?scope=system")
    assert system_list.status_code == 200
    assert all(item["scope"] == "system" for item in system_list.json())
    owner_list = await client.get(f"/api/v1/agents?owner_user_id={owner_id}")
    assert owner_list.status_code == 200
    assert [item["id"] for item in owner_list.json()] == [str(personal_id)]

    updated = await client.patch(
        f"/api/v1/agents/{system_id}", json={"name": "Updated API Agent"}
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated API Agent"

    duplicate = await client.post("/api/v1/agents", json=system_payload)
    assert duplicate.status_code == 409
    assert (await client.post("/api/v1/agents", json=agent_payload(scope="invalid"))).status_code == 422
    assert (await client.post("/api/v1/agents", json=agent_payload(scope="personal"))).status_code == 422
    assert (await client.post(
        "/api/v1/agents",
        json=agent_payload(scope="personal", owner_user_id=str(uuid4())),
    )).status_code == 404
    assert (await client.post(
        "/api/v1/agents", json=agent_payload(model_config_id=str(uuid4()))
    )).status_code == 404
    assert (await client.get(f"/api/v1/agents/{uuid4()}")).status_code == 404
    assert (await client.get("/api/v1/agents/not-a-uuid")).status_code == 422

    assert (await client.patch(
        f"/api/v1/agents/{personal_id}", json={"owner_user_id": None}
    )).status_code == 422
    assert (await client.patch(
        f"/api/v1/agents/{system_id}", json={"scope": "personal"}
    )).status_code == 422
    assert (await client.patch(
        f"/api/v1/agents/{system_id}", json={"model_config_id": str(uuid4())}
    )).status_code == 404
    assert (await client.patch(
        f"/api/v1/agents/{system_id}", json={"code": personal.json()["code"]}
    )).status_code == 409

    deleted = await client.delete(f"/api/v1/agents/{system_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""


@pytest.mark.asyncio
async def test_agent_pagination_validation(api_context: tuple) -> None:
    client, track_id = api_context
    for _ in range(3):
        response = await client.post("/api/v1/agents", json=agent_payload())
        assert response.status_code == 201
        track_id(Agent, UUID(response.json()["id"]))

    response = await client.get("/api/v1/agents?offset=0&limit=2")
    assert response.status_code == 200
    assert len(response.json()) == 2
    for query in ("limit=0", "limit=101", "offset=-1"):
        assert (await client.get(f"/api/v1/agents?{query}")).status_code == 422
