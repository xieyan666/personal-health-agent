"""Real PostgreSQL integration tests for Message API."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.app.models import Agent, Conversation, Message, User
from backend.tests.api.test_conversations import (
    agent_payload,
    conversation_payload,
    user_payload,
)


def message_payload(conversation_id: UUID, **overrides: object) -> dict:
    values = {
        "conversation_id": str(conversation_id),
        "parent_message_id": None,
        "role": "user",
        "content": "test message",
        "content_data": {},
        "status": "completed",
        "source_type": "user",
        "source_reference": {},
        "risk_level": "low",
        "safety_status": "passed",
    }
    values.update(overrides)
    return values


async def setup_conversation(client: object, track_id: object) -> UUID:
    user = await client.post("/api/v1/users", json=user_payload())
    user_id = UUID(user.json()["id"])
    track_id(User, user_id)
    agent = await client.post("/api/v1/agents", json=agent_payload())
    agent_id = UUID(agent.json()["id"])
    track_id(Agent, agent_id)
    conversation = await client.post(
        "/api/v1/conversations", json=conversation_payload(user_id, agent_id)
    )
    conversation_id = UUID(conversation.json()["id"])
    track_id(Conversation, conversation_id)
    return conversation_id


async def create_message(
    client: object, track_id: object, conversation_id: UUID, **overrides: object
) -> UUID:
    response = await client.post(
        "/api/v1/messages", json=message_payload(conversation_id, **overrides)
    )
    assert response.status_code == 201
    message_id = UUID(response.json()["id"])
    track_id(Message, message_id)
    return message_id


@pytest.mark.asyncio
async def test_message_crud_order_children_and_errors(api_context: tuple) -> None:
    client, track_id = api_context
    first_conversation = await setup_conversation(client, track_id)
    second_conversation = await setup_conversation(client, track_id)
    first = await create_message(client, track_id, first_conversation, content="hello")
    second = await create_message(client, track_id, first_conversation, role="assistant", content="assistant reply")
    third = await create_message(client, track_id, first_conversation, role="system", content="system test")

    fetched = await client.get(f"/api/v1/messages/{first}")
    assert fetched.status_code == 200
    assert fetched.json()["content"] == "hello"
    ordered = await client.get(
        "/api/v1/messages", params={"conversation_id": str(first_conversation)}
    )
    assert [UUID(item["id"]) for item in ordered.json()] == [first, second, third]

    child_one = await create_message(
        client, track_id, first_conversation, parent_message_id=str(first)
    )
    child_two = await create_message(
        client, track_id, first_conversation, parent_message_id=str(first)
    )
    await create_message(
        client, track_id, first_conversation, parent_message_id=str(child_one)
    )
    children = await client.get(
        "/api/v1/messages", params={"parent_message_id": str(first)}
    )
    assert [UUID(item["id"]) for item in children.json()] == [child_one, child_two]

    assert (await client.post(
        "/api/v1/messages", json=message_payload(uuid4())
    )).status_code == 404
    assert (await client.post(
        "/api/v1/messages",
        json=message_payload(first_conversation, parent_message_id=str(uuid4())),
    )).status_code == 404
    assert (await client.post(
        "/api/v1/messages",
        json=message_payload(second_conversation, parent_message_id=str(first)),
    )).status_code == 422
    assert (await client.post(
        "/api/v1/messages", json=message_payload(first_conversation, role="invalid")
    )).status_code == 422
    assert (await client.get(f"/api/v1/messages/{uuid4()}")).status_code == 404
    assert (await client.get("/api/v1/messages/not-a-uuid")).status_code == 422
    conflict = await client.get(
        "/api/v1/messages",
        params={
            "conversation_id": str(first_conversation),
            "parent_message_id": str(first),
        },
    )
    assert conflict.status_code == 422
    for query in ("limit=0", "limit=101", "offset=-1"):
        assert (await client.get(f"/api/v1/messages?{query}")).status_code == 422

    standalone = await create_message(client, track_id, second_conversation)
    deleted = await client.delete(f"/api/v1/messages/{standalone}")
    assert deleted.status_code == 204
    assert deleted.content == b""


@pytest.mark.asyncio
async def test_conversation_and_parent_message_delete_conflicts(api_context: tuple) -> None:
    client, track_id = api_context
    conversation_id = await setup_conversation(client, track_id)
    parent_id = await create_message(client, track_id, conversation_id)
    child_id = await create_message(
        client, track_id, conversation_id, parent_message_id=str(parent_id)
    )

    conversation_delete = await client.delete(
        f"/api/v1/conversations/{conversation_id}"
    )
    assert conversation_delete.status_code == 409
    parent_delete = await client.delete(f"/api/v1/messages/{parent_id}")
    assert parent_delete.status_code == 409
    assert (await client.get(f"/api/v1/conversations/{conversation_id}")).status_code == 200
    assert (await client.get(f"/api/v1/messages/{parent_id}")).status_code == 200
    assert (await client.get(f"/api/v1/messages/{child_id}")).status_code == 200
