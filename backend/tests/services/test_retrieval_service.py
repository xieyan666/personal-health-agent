from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient, models

from backend.app.core.config import get_settings
from backend.app.models import DocumentChunk
from backend.app.services.exceptions import NotFoundError, ValidationError
from backend.app.services.qdrant_index import QdrantIndexService
from backend.app.services.retrieval import RetrievalService
from backend.tests.services.test_qdrant_index_service import _setup


@pytest.mark.asyncio
async def test_retrieval_uses_postgres_content_and_scope(service_context):
    session, track = service_context
    config, kb, first, second, chunks = await _setup(session, track)
    client = AsyncQdrantClient(url=get_settings().qdrant_url, api_key=get_settings().qdrant_api_key)
    try:
        indexer = QdrantIndexService(session, client)
        await indexer.index_document(first.id, config.id)
        await indexer.index_document(second.id, config.id)
        results = await RetrievalService(session, client).retrieve(kb.id, "alpha", config.id, top_k=2)
        assert len(results) == 2
        assert [item.score for item in results] == sorted((item.score for item in results), reverse=True)
        assert {item.content for item in results} <= {chunk.content for chunk in chunks}
        assert all(item.document_id in {first.id, second.id} for item in results)
        with pytest.raises(ValidationError): await RetrievalService(session, client).retrieve(kb.id, " ", config.id)
        with pytest.raises(NotFoundError): await RetrievalService(session, client).retrieve(uuid4(), "alpha", config.id)
    finally:
        if await client.collection_exists(kb.vector_collection): await client.delete_collection(kb.vector_collection)
        await client.close()


@pytest.mark.asyncio
async def test_retrieval_empty_collection_and_stale_point(service_context):
    session, track = service_context
    config, kb, first, _, chunks = await _setup(session, track)
    client = AsyncQdrantClient(url=get_settings().qdrant_url, api_key=get_settings().qdrant_api_key)
    try:
        service = RetrievalService(session, client)
        assert await service.retrieve(kb.id, "alpha", config.id) == []
        await QdrantIndexService(session, client).index_document(first.id, config.id)
        await session.delete(chunks[0]); await session.commit()
        results = await service.retrieve(kb.id, "alpha", config.id)
        assert all(item.chunk_id != chunks[0].id for item in results)
    finally:
        if await client.collection_exists(kb.vector_collection): await client.delete_collection(kb.vector_collection)
        await client.close()
