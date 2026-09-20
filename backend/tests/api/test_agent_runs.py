"""Real PostgreSQL integration tests for the AgentRun API."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.app.core.database import AsyncSessionFactory
from backend.app.models import Agent, AgentRun, AuditLog, Conversation, Message, User
from backend.tests.api.test_conversations import agent_payload, conversation_payload, user_payload
from backend.tests.api.test_messages import message_payload


async def setup_conversation(client: object, track_id: object) -> tuple[UUID, UUID, UUID]:
    user = await client.post("/api/v1/users", json=user_payload())
    assert user.status_code == 201
    user_id = UUID(user.json()["id"])
    track_id(User, user_id)
    agent = await client.post("/api/v1/agents", json=agent_payload())
    assert agent.status_code == 201
    agent_id = UUID(agent.json()["id"])
    track_id(Agent, agent_id)
    conversation = await client.post(
        "/api/v1/conversations", json=conversation_payload(user_id, agent_id)
    )
    assert conversation.status_code == 201
    conversation_id = UUID(conversation.json()["id"])
    track_id(Conversation, conversation_id)
    return user_id, agent_id, conversation_id


async def create_message(
    client: object, track_id: object, conversation_id: UUID
) -> UUID:
    response = await client.post(
        "/api/v1/messages", json=message_payload(conversation_id)
    )
    assert response.status_code == 201
    message_id = UUID(response.json()["id"])
    track_id(Message, message_id)
    return message_id


def run_payload(
    user_id: UUID, agent_id: UUID, conversation_id: UUID, **overrides: object
) -> dict:
    values = {
        "user_id": str(user_id),
        "agent_id": str(agent_id),
        "conversation_id": str(conversation_id),
        "trigger_message_id": None,
        "parent_run_id": None,
        "model_config_id": None,
        "status": "pending",
        "input_summary": "test input",
        "risk_level": "low",
        "safety_status": "pending",
    }
    values.update(overrides)
    return values


async def create_run(
    client: object,
    track_id: object,
    user_id: UUID,
    agent_id: UUID,
    conversation_id: UUID,
    **overrides: object,
) -> tuple[UUID, dict]:
    response = await client.post(
        "/api/v1/agent-runs",
        json=run_payload(user_id, agent_id, conversation_id, **overrides),
    )
    assert response.status_code == 201, response.text
    run_id = UUID(response.json()["id"])
    track_id(AgentRun, run_id)
    return run_id, response.json()


@pytest.mark.asyncio
async def test_agent_run_crud_status_filters_and_order(api_context: tuple) -> None:
    client, track_id = api_context
    user_id, agent_id, conversation_id = await setup_conversation(client, track_id)
    first_id, _ = await create_run(
        client, track_id, user_id, agent_id, conversation_id
    )
    second_id, _ = await create_run(
        client, track_id, user_id, agent_id, conversation_id
    )

    listed = await client.get("/api/v1/agent-runs")
    assert listed.status_code == 200
    listed_ids = [UUID(item["id"]) for item in listed.json()]
    assert listed_ids.index(second_id) < listed_ids.index(first_id)
    filtered = await client.get(
        "/api/v1/agent-runs",
        params={"agent_id": str(agent_id), "status": "pending"},
    )
    assert {UUID(item["id"]) for item in filtered.json()} >= {first_id, second_id}
    assert (await client.get(
        "/api/v1/agent-runs",
        params={"agent_id": str(agent_id), "conversation_id": str(conversation_id)},
    )).status_code == 422
    assert (await client.get(
        "/api/v1/agent-runs", params={"status": "invalid"}
    )).status_code == 422

    running = await client.patch(
        f"/api/v1/agent-runs/{first_id}", json={"status": "running"}
    )
    assert running.status_code == 200
    assert running.json()["started_at"] is not None
    assert running.json()["finished_at"] is None
    succeeded = await client.patch(
        f"/api/v1/agent-runs/{first_id}",
        json={
            "status": "succeeded",
            "output_summary": "test output",
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "latency_ms": 3,
        },
    )
    assert succeeded.status_code == 200
    assert succeeded.json()["started_at"] == running.json()["started_at"]
    assert succeeded.json()["finished_at"] is not None
    assert (await client.patch(
        f"/api/v1/agent-runs/{first_id}", json={"status": "running"}
    )).status_code == 422
    assert (await client.patch(
        f"/api/v1/agent-runs/{second_id}", json={"prompt_tokens": -1}
    )).status_code == 422

    fetched = await client.get(f"/api/v1/agent-runs/{first_id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "succeeded"
    assert (await client.get(f"/api/v1/agent-runs/{uuid4()}")).status_code == 404
    assert (await client.get("/api/v1/agent-runs/not-a-uuid")).status_code == 422
    for query in ("limit=0", "limit=101", "offset=-1"):
        assert (await client.get(f"/api/v1/agent-runs?{query}")).status_code == 422

    deleted = await client.delete(f"/api/v1/agent-runs/{second_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""


@pytest.mark.asyncio
async def test_agent_run_create_relationship_validation(api_context: tuple) -> None:
    client, track_id = api_context
    user_a, agent_a, conversation_a = await setup_conversation(client, track_id)
    user_b, agent_b, conversation_b = await setup_conversation(client, track_id)
    message_a = await create_message(client, track_id, conversation_a)
    message_b = await create_message(client, track_id, conversation_b)
    parent_b, _ = await create_run(
        client, track_id, user_b, agent_b, conversation_b
    )

    cases = [
        (run_payload(user_a, uuid4(), conversation_a), 404),
        (run_payload(user_a, agent_a, uuid4()), 404),
        (run_payload(user_a, agent_b, conversation_a), 422),
        (run_payload(user_a, agent_a, conversation_a, trigger_message_id=str(uuid4())), 404),
        (run_payload(user_a, agent_a, conversation_a, trigger_message_id=str(message_b)), 422),
        (run_payload(user_a, agent_a, conversation_a, parent_run_id=str(uuid4())), 404),
        (run_payload(user_a, agent_a, conversation_a, parent_run_id=str(parent_b)), 422),
        (run_payload(user_a, agent_a, conversation_a, model_config_id=str(uuid4())), 404),
        (run_payload(user_a, agent_a, conversation_a, status="invalid"), 422),
    ]
    for payload, expected in cases:
        response = await client.post("/api/v1/agent-runs", json=payload)
        assert response.status_code == expected, response.text

    run_id, _ = await create_run(
        client,
        track_id,
        user_a,
        agent_a,
        conversation_a,
        trigger_message_id=str(message_a),
    )
    assert (await client.patch(
        f"/api/v1/agent-runs/{run_id}",
        json={"output_message_id": str(message_b)},
    )).status_code == 422
    same_conversation = await client.patch(
        f"/api/v1/agent-runs/{run_id}",
        json={"output_message_id": str(message_a)},
    )
    assert same_conversation.status_code == 200
    assert same_conversation.json()["output_message_id"] == str(message_a)


@pytest.mark.asyncio
async def test_agent_run_children_and_delete_conflicts(api_context: tuple) -> None:
    client, track_id = api_context
    user_id, agent_id, conversation_id = await setup_conversation(client, track_id)
    parent_id, _ = await create_run(
        client, track_id, user_id, agent_id, conversation_id
    )
    child_id, _ = await create_run(
        client,
        track_id,
        user_id,
        agent_id,
        conversation_id,
        parent_run_id=str(parent_id),
    )
    grandchild_id, _ = await create_run(
        client,
        track_id,
        user_id,
        agent_id,
        conversation_id,
        parent_run_id=str(child_id),
    )
    children = await client.get(
        "/api/v1/agent-runs", params={"parent_run_id": str(parent_id)}
    )
    assert [UUID(item["id"]) for item in children.json()] == [child_id]
    assert grandchild_id not in [UUID(item["id"]) for item in children.json()]

    parent_delete = await client.delete(f"/api/v1/agent-runs/{parent_id}")
    assert parent_delete.status_code == 409
    assert (await client.get(f"/api/v1/agent-runs/{parent_id}")).status_code == 200
    assert (await client.get(f"/api/v1/agent-runs/{child_id}")).status_code == 200

    audited_id, audited = await create_run(
        client, track_id, user_id, agent_id, conversation_id
    )
    audit_id = uuid4()
    async with AsyncSessionFactory() as session:
        session.add(
            AuditLog(
                id=audit_id,
                actor_user_id=user_id,
                action="test.audit",
                resource_type="agent_run",
                resource_id=audited_id,
                agent_run_id=audited_id,
                risk_level="low",
                safety_status="passed",
                outcome="success",
                details={},
                trace_id=UUID(audited["trace_id"]),
            )
        )
        await session.commit()
    track_id(AuditLog, audit_id)
    audit_delete = await client.delete(f"/api/v1/agent-runs/{audited_id}")
    assert audit_delete.status_code == 409
    assert (await client.get(f"/api/v1/agent-runs/{audited_id}")).status_code == 200
