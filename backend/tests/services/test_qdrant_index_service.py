"""Real PostgreSQL and Qdrant integration tests for chunk indexing."""

from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient, models

from backend.app.core.config import get_settings
from backend.app.models import Document, DocumentChunk, KnowledgeBase, ModelConfig, ModelProvider, User
from backend.app.services.exceptions import NotFoundError, ServiceError
from backend.app.services.qdrant_index import QdrantIndexService


async def _setup(session, track):
    suffix = uuid4().hex
    user = track(User(id=uuid4(), username=f"index-{suffix}", display_name="Index", email=f"index-{suffix}@example.com", auth_source="local"))
    provider = track(ModelProvider(id=uuid4(), name=f"fake-{suffix}", provider_type="fake", status="active", config={}))
    config = track(ModelConfig(id=uuid4(), provider_id=provider.id, name=f"embedding-{suffix}", model_name="fake-8", model_type="embedding", status="active", parameters={}))
    collection = f"test_chunks_{suffix}"
    kb = track(KnowledgeBase(id=uuid4(), owner_user_id=user.id, name=f"kb-{suffix}", status="active", vector_collection=collection, retrieval_config={}))
    first = track(Document(id=uuid4(), knowledge_base_id=kb.id, name="one", source_type="upload", source_reference={}, status="stored", metadata_={}))
    second = track(Document(id=uuid4(), knowledge_base_id=kb.id, name="two", source_type="upload", source_reference={}, status="stored", metadata_={}))
    session.add_all([user, provider, config, kb, first, second])
    await session.flush()
    chunks = []
    for document, contents in ((first, ["alpha", "beta"]), (second, ["gamma"])):
        for index, content in enumerate(contents):
            chunk = track(DocumentChunk(id=uuid4(), document_id=document.id, chunk_index=index, content=content, char_count=len(content)))
            session.add(chunk)
            chunks.append(chunk)
    await session.commit()
    return config, kb, first, second, chunks


@pytest.mark.asyncio
async def test_qdrant_document_index_lifecycle(service_context):
    session, track = service_context
    config, kb, first, second, chunks = await _setup(session, track)
    settings = get_settings()
    client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    try:
        service = QdrantIndexService(session, client)
        indexed = await service.index_document(first.id, config.id)
        assert indexed.collection_name == kb.vector_collection
        assert indexed.indexed_count == 2
        assert indexed.dimension == 8
        info = await client.get_collection(kb.vector_collection)
        assert info.config.params.vectors.size == 8
        assert info.config.params.vectors.distance == models.Distance.COSINE
        points = await client.retrieve(kb.vector_collection, ids=[str(chunk.id) for chunk in chunks[:2]], with_payload=True)
        assert {str(point.id) for point in points} == {str(chunk.id) for chunk in chunks[:2]}
        for point in points:
            assert set(point.payload) == {"chunk_id", "document_id", "knowledge_base_id", "chunk_index"}
            assert "content" not in point.payload
        await service.index_document(first.id, config.id)
        count = await client.count(kb.vector_collection, count_filter=models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=str(first.id)))]), exact=True)
        assert count.count == 2
        await service.index_document(second.id, config.id)
        await service.delete_document_index(first.id)
        assert (await client.count(kb.vector_collection, count_filter=models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=str(first.id)))]), exact=True)).count == 0
        assert (await client.count(kb.vector_collection, count_filter=models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=str(second.id)))]), exact=True)).count == 1
        assert await session.get(DocumentChunk, chunks[0].id) is not None
    finally:
        if await client.collection_exists(kb.vector_collection):
            await client.delete_collection(kb.vector_collection)
        await client.close()


@pytest.mark.asyncio
async def test_qdrant_index_missing_document_and_empty_document(service_context):
    session, track = service_context
    config, kb, first, _, _ = await _setup(session, track)
    settings = get_settings()
    client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    service = QdrantIndexService(session, client)
    with pytest.raises(NotFoundError):
        await service.index_document(uuid4(), config.id)
    empty = track(Document(id=uuid4(), knowledge_base_id=kb.id, name="empty", source_type="upload", source_reference={}, status="stored", metadata_={}))
    session.add(empty)
    await session.commit()
    try:
        result = await service.index_document(empty.id, config.id)
        assert result.indexed_count == 0
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_qdrant_index_rejects_collection_dimension_mismatch(service_context):
    session, track = service_context
    config, kb, first, _, _ = await _setup(session, track)
    settings = get_settings()
    client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    try:
        await client.create_collection(
            collection_name=kb.vector_collection,
            vectors_config=models.VectorParams(size=4, distance=models.Distance.COSINE),
        )
        with pytest.raises(ServiceError, match="vector size"):
            await QdrantIndexService(session, client).index_document(first.id, config.id)
    finally:
        if await client.collection_exists(kb.vector_collection):
            await client.delete_collection(kb.vector_collection)
        await client.close()
