from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_agent_rag_run_and_stream_keep_existing_validation(api_context):
    client, _ = api_context
    payload = {"user_id": str(uuid4()), "conversation_id": str(uuid4()), "content": ""}
    run_response = await client.post(f"/api/v1/agents/{uuid4()}/run", json=payload)
    stream_response = await client.post(f"/api/v1/agents/{uuid4()}/stream", json=payload)
    assert run_response.status_code == 422
    assert stream_response.status_code == 422
