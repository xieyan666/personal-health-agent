from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_agent_stream_request_validation(api_context):
    client, _ = api_context
    response = await client.post(f"/api/v1/agents/{uuid4()}/stream", json={"user_id": str(uuid4()), "conversation_id": str(uuid4()), "content": ""})
    assert response.status_code == 422
