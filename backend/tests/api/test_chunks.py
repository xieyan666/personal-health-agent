from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from backend.app.core.database import AsyncSessionFactory
from backend.app.models import Document, DocumentChunk
from backend.app.services.chunk import ChunkService


@pytest.mark.asyncio
async def test_chunks_query_and_missing_document(api_context):
    client, track_id = api_context
    response = await client.get(f"/api/v1/documents/{uuid4()}/chunks")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_chunks_query_returns_ordered_rows(api_context):
    client, track_id = api_context
    from backend.tests.api.test_documents import setup_knowledge_base
    kb_id = await setup_knowledge_base(client, track_id)
    upload = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"file": ("chunk.txt", b"source", "text/plain")},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]
    document_uuid = UUID(document_id)
    track_id(Document, document_uuid)
    async with AsyncSessionFactory() as session:
        await ChunkService(session).create_chunks(document_uuid, "a" * 1200)
    response = await client.get(f"/api/v1/documents/{document_id}/chunks")
    assert response.status_code == 200
    body = response.json()
    assert [item["chunk_index"] for item in body] == [0, 1]
    assert "source_reference" not in upload.json()
