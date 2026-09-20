"""Real PostgreSQL integration tests for Model Provider API."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.app.models import ModelConfig, ModelProvider


def provider_payload(**overrides: object) -> dict:
    values = {
        "name": f"api_provider_{uuid4().hex}",
        "provider_type": "openai-compatible",
        "status": "active",
        "endpoint": "https://models.example.test/v1",
        "secret_ref": "secret://models/test",
        "config": {},
    }
    values.update(overrides)
    return values


def config_payload(provider_id: UUID, **overrides: object) -> dict:
    values = {
        "provider_id": str(provider_id),
        "name": f"api_config_{uuid4().hex}",
        "model_name": "test-model",
        "model_type": "chat",
        "status": "active",
        "parameters": {},
    }
    values.update(overrides)
    return values


@pytest.mark.asyncio
async def test_model_provider_crud_security_and_errors(api_context: tuple) -> None:
    client, track_id = api_context
    payload = provider_payload()
    created = await client.post("/api/v1/model-providers", json=payload)
    assert created.status_code == 201
    provider_id = UUID(created.json()["id"])
    track_id(ModelProvider, provider_id)
    assert created.json()["secret_ref"] == payload["secret_ref"]

    fetched = await client.get(f"/api/v1/model-providers/{provider_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == payload["name"]
    listed = await client.get("/api/v1/model-providers?offset=0&limit=2")
    assert listed.status_code == 200
    assert len(listed.json()) <= 2

    updated = await client.patch(
        f"/api/v1/model-providers/{provider_id}",
        json={"status": "inactive"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "inactive"
    assert updated.json()["endpoint"] == payload["endpoint"]

    duplicate = await client.post("/api/v1/model-providers", json=payload)
    assert duplicate.status_code == 409
    second = await client.post("/api/v1/model-providers", json=provider_payload())
    assert second.status_code == 201
    second_id = UUID(second.json()["id"])
    track_id(ModelProvider, second_id)
    rename_conflict = await client.patch(
        f"/api/v1/model-providers/{second_id}", json={"name": payload["name"]}
    )
    assert rename_conflict.status_code == 409

    api_key_payload = provider_payload(api_key="plaintext-key")
    assert (await client.post("/api/v1/model-providers", json=api_key_payload)).status_code == 422
    unknown_payload = provider_payload(unknown_field=True)
    assert (await client.post("/api/v1/model-providers", json=unknown_payload)).status_code == 422
    assert (await client.get(f"/api/v1/model-providers/{uuid4()}")).status_code == 404
    assert (await client.get("/api/v1/model-providers/not-a-uuid")).status_code == 422
    for query in ("limit=0", "limit=101", "offset=-1"):
        assert (await client.get(f"/api/v1/model-providers?{query}")).status_code == 422

    deleted = await client.delete(f"/api/v1/model-providers/{provider_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""


@pytest.mark.asyncio
async def test_referenced_model_provider_delete_is_blocked(api_context: tuple) -> None:
    client, track_id = api_context
    provider = await client.post("/api/v1/model-providers", json=provider_payload())
    provider_id = UUID(provider.json()["id"])
    track_id(ModelProvider, provider_id)
    config = await client.post(
        "/api/v1/model-configs", json=config_payload(provider_id)
    )
    assert config.status_code == 201
    config_id = UUID(config.json()["id"])
    track_id(ModelConfig, config_id)

    blocked = await client.delete(f"/api/v1/model-providers/{provider_id}")
    assert blocked.status_code == 409
    assert blocked.json() == {
        "detail": "Model provider is referenced by model configs"
    }
    assert (await client.get(f"/api/v1/model-providers/{provider_id}")).status_code == 200
    assert (await client.get(f"/api/v1/model-configs/{config_id}")).status_code == 200
