import pytest


@pytest.mark.asyncio
async def test_retrieval_validation_errors(api_context):
    client, _ = api_context
    response = await client.post("/api/v1/knowledge-bases/00000000-0000-0000-0000-000000000000/retrieve", json={"query":"x","model_config_id":"00000000-0000-0000-0000-000000000000","top_k":0})
    assert response.status_code == 422
    response = await client.post("/api/v1/knowledge-bases/00000000-0000-0000-0000-000000000000/rag-context", json={"query":"","model_config_id":"00000000-0000-0000-0000-000000000000"})
    assert response.status_code == 422
