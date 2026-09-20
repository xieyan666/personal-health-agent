"""Real PostgreSQL integration tests for Model Config API."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.app.models import Agent, ModelConfig, ModelProvider


def provider_payload() -> dict:
    return {
        "name": f"config_provider_{uuid4().hex}",
        "provider_type": "test",
        "status": "active",
        "endpoint": None,
        "secret_ref": "secret://models/config-test",
        "config": {},
    }


def config_payload(provider_id: UUID, **overrides: object) -> dict:
    values = {
        "provider_id": str(provider_id),
        "name": f"api_config_{uuid4().hex}",
        "model_name": "test-model",
        "model_type": "chat",
        "status": "active",
        "parameters": {"temperature": 0.7},
    }
    values.update(overrides)
    return values


def agent_payload(model_config_id: UUID) -> dict:
    return {
        "code": f"config_agent_{uuid4().hex}",
        "name": "Config Reference Agent",
        "scope": "system",
        "owner_user_id": None,
        "category": "daily_health",
        "status": "active",
        "model_config_id": str(model_config_id),
        "config": {},
        "version": 1,
    }


async def create_provider(client: object, track_id: object) -> UUID:
    response = await client.post("/api/v1/model-providers", json=provider_payload())
    assert response.status_code == 201
    provider_id = UUID(response.json()["id"])
    track_id(ModelProvider, provider_id)
    return provider_id


@pytest.mark.asyncio
async def test_model_config_crud_relationship_and_errors(api_context: tuple) -> None:
    client, track_id = api_context
    provider_id = await create_provider(client, track_id)
    payload = config_payload(provider_id)
    created = await client.post("/api/v1/model-configs", json=payload)
    assert created.status_code == 201
    config_id = UUID(created.json()["id"])
    track_id(ModelConfig, config_id)

    fetched = await client.get(f"/api/v1/model-configs/{config_id}")
    assert fetched.status_code == 200
    assert fetched.json()["provider_id"] == str(provider_id)
    listed = await client.get("/api/v1/model-configs?offset=0&limit=2")
    assert listed.status_code == 200
    assert len(listed.json()) <= 2

    updated = await client.patch(
        f"/api/v1/model-configs/{config_id}",
        json={"parameters": {"temperature": 0.2}},
    )
    assert updated.status_code == 200
    assert updated.json()["parameters"] == {"temperature": 0.2}

    duplicate = await client.post("/api/v1/model-configs", json=payload)
    assert duplicate.status_code == 409
    assert (await client.post(
        "/api/v1/model-configs", json=config_payload(uuid4())
    )).status_code == 404
    assert (await client.patch(
        f"/api/v1/model-configs/{config_id}",
        json={"provider_id": str(uuid4())},
    )).status_code == 404
    assert (await client.get(f"/api/v1/model-configs/{uuid4()}")).status_code == 404
    assert (await client.get("/api/v1/model-configs/not-a-uuid")).status_code == 422
    assert (await client.post(
        "/api/v1/model-configs",
        json=config_payload(provider_id, unknown_field=True),
    )).status_code == 422
    for query in ("limit=0", "limit=101", "offset=-1"):
        assert (await client.get(f"/api/v1/model-configs?{query}")).status_code == 422

    deleted = await client.delete(f"/api/v1/model-configs/{config_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""


@pytest.mark.asyncio
async def test_provider_filter_and_agent_model_config_fk(api_context: tuple) -> None:
    client, track_id = api_context
    provider_a = await create_provider(client, track_id)
    provider_b = await create_provider(client, track_id)
    config_ids = []
    for provider_id in (provider_a, provider_a, provider_b):
        response = await client.post(
            "/api/v1/model-configs", json=config_payload(provider_id)
        )
        assert response.status_code == 201
        config_id = UUID(response.json()["id"])
        config_ids.append(config_id)
        track_id(ModelConfig, config_id)

    filtered = await client.get(
        "/api/v1/model-configs", params={"provider_id": str(provider_a)}
    )
    assert filtered.status_code == 200
    assert {UUID(item["id"]) for item in filtered.json()} == set(config_ids[:2])

    agent = await client.post(
        "/api/v1/agents", json=agent_payload(config_ids[0])
    )
    assert agent.status_code == 201
    agent_id = UUID(agent.json()["id"])
    track_id(Agent, agent_id)
    assert agent.json()["model_config_id"] == str(config_ids[0])

    config_delete = await client.delete(f"/api/v1/model-configs/{config_ids[0]}")
    assert config_delete.status_code == 409
    assert config_delete.json() == {
        "detail": "Model config is referenced by agents"
    }
    provider_delete = await client.delete(f"/api/v1/model-providers/{provider_a}")
    assert provider_delete.status_code == 409
    assert (await client.get(f"/api/v1/model-configs/{config_ids[0]}")).status_code == 200
    assert (await client.get(f"/api/v1/agents/{agent_id}")).status_code == 200
