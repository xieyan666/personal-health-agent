import pytest
from qdrant_client import AsyncQdrantClient

from backend.app.core.config import get_settings
from backend.app.services.qdrant_index import QdrantIndexService
from backend.app.services.rag import RagService
from backend.app.services.retrieval import RetrievalService
from backend.tests.services.test_qdrant_index_service import _setup


@pytest.mark.asyncio
async def test_rag_context_preserves_retrieval_order(service_context):
    session, track = service_context
    config, kb, first, _, _ = await _setup(session, track)
    client = AsyncQdrantClient(url=get_settings().qdrant_url, api_key=get_settings().qdrant_api_key)
    try:
        await QdrantIndexService(session, client).index_document(first.id, config.id)
        context = await RagService(session, RetrievalService(session, client)).build_context(kb.id, "alpha", config.id)
        assert context.context_text
        assert all(f"--- chunk {chunk.chunk_index} ---" in context.context_text for chunk in context.chunks)
    finally:
        if await client.collection_exists(kb.vector_collection): await client.delete_collection(kb.vector_collection)
        await client.close()
