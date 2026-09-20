"""Real PostgreSQL integration tests for Conversation API."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.app.models import Agent, Conversation, User


def user_payload() -> dict:
    token = uuid4().hex
    return {
        "username": f"conversation_user_{token}",
        "display_name": "Conversation User",
        "email": f"{token}@example.test",
        "auth_source": "local",
        "status": "active",
        "timezone": "Asia/Shanghai",
    }


def agent_payload() -> dict:
    return {
        "code": f"conversation_agent_{uuid4().hex}",
        "name": "Conversation Agent",
        "scope": "system",
        "owner_user_id": None,
        "category": "daily_health",
        "status": "active",
        "config": {},
        "version": 1,
    }


def conversation_payload(user_id: UUID, agent_id: UUID, **overrides: object) -> dict:
    values = {
        "user_id": str(user_id),
        "agent_id": str(agent_id),
        "title": "Test Conversation",
        "status": "active",
        "context": {},
    }
    values.update(overrides)
    return values


async def create_user(client: object, track_id: object) -> UUID:
    response = await client.post("/api/v1/users", json=user_payload())
    assert response.status_code == 201
    object_id = UUID(response.json()["id"])
    track_id(User, object_id)
    return object_id


async def create_agent(client: object, track_id: object) -> UUID:
    response = await client.post("/api/v1/agents", json=agent_payload())
    assert response.status_code == 201
    object_id = UUID(response.json()["id"])
    track_id(Agent, object_id)
    return object_id


async def create_conversation(
    client: object, track_id: object, user_id: UUID, agent_id: UUID
) -> UUID:
    response = await client.post(
        "/api/v1/conversations", json=conversation_payload(user_id, agent_id)
    )
    assert response.status_code == 201
    object_id = UUID(response.json()["id"])
    track_id(Conversation, object_id)
    return object_id


@pytest.mark.asyncio
async def test_conversation_crud_and_errors(api_context: tuple) -> None:
    client, track_id = api_context
    user_id = await create_user(client, track_id)
    agent_id = await create_agent(client, track_id)
    conversation_id = await create_conversation(client, track_id, user_id, agent_id)

    fetched = await client.get(f"/api/v1/conversations/{conversation_id}")
    assert fetched.status_code == 200
    assert fetched.json()["user_id"] == str(user_id)
    listed = await client.get("/api/v1/conversations?offset=0&limit=2")
    assert listed.status_code == 200
    assert len(listed.json()) <= 2

    updated = await client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "Updated Conversation", "context": {"test": True}},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated Conversation"
    assert updated.json()["context"] == {"test": True}
    assert (await client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"user_id": str(uuid4())},
    )).status_code == 422

    assert (await client.post(
        "/api/v1/conversations", json=conversation_payload(uuid4(), agent_id)
    )).status_code == 404
    assert (await client.post(
        "/api/v1/conversations", json=conversation_payload(user_id, uuid4())
    )).status_code == 404
    assert (await client.get(f"/api/v1/conversations/{uuid4()}")).status_code == 404
    assert (await client.get("/api/v1/conversations/not-a-uuid")).status_code == 422
    for query in ("limit=0", "limit=101", "offset=-1"):
        assert (await client.get(f"/api/v1/conversations?{query}")).status_code == 422

    deleted = await client.delete(f"/api/v1/conversations/{conversation_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""


@pytest.mark.asyncio
async def test_conversation_filters_and_updated_order(api_context: tuple) -> None:
    client, track_id = api_context
    user_a = await create_user(client, track_id)
    user_b = await create_user(client, track_id)
    agent_a = await create_agent(client, track_id)
    agent_b = await create_agent(client, track_id)
    a1 = await create_conversation(client, track_id, user_a, agent_a)
    a2 = await create_conversation(client, track_id, user_a, agent_b)
    b1 = await create_conversation(client, track_id, user_b, agent_a)

    patched = await client.patch(
        f"/api/v1/conversations/{a1}", json={"title": "Most Recent"}
    )
    assert patched.status_code == 200
    all_items = (await client.get("/api/v1/conversations")).json()
    assert UUID(all_items[0]["id"]) == a1

    by_user = await client.get(
        "/api/v1/conversations", params={"user_id": str(user_a)}
    )
    assert {UUID(item["id"]) for item in by_user.json()} == {a1, a2}
    by_agent = await client.get(
        "/api/v1/conversations", params={"agent_id": str(agent_a)}
    )
    assert {UUID(item["id"]) for item in by_agent.json()} == {a1, b1}
    combined = await client.get(
        "/api/v1/conversations",
        params={"user_id": str(user_a), "agent_id": str(agent_a)},
    )
    assert [UUID(item["id"]) for item in combined.json()] == [a1]
