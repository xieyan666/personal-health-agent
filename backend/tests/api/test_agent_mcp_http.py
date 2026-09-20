import pytest
from uuid import uuid4

@pytest.mark.asyncio
async def test_http_mcp_agent_route_validation_unchanged(api_context):
    client, _ = api_context
    payload = {"user_id": str(uuid4()), "conversation_id": str(uuid4()), "content": ""}
    assert (await client.post(f"/api/v1/agents/{uuid4()}/run", json=payload)).status_code == 422
    assert (await client.post(f"/api/v1/agents/{uuid4()}/stream", json=payload)).status_code == 422
