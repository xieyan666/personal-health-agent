from uuid import uuid4

import pytest

from backend.app.services.embedding import EmbeddingService
from types import SimpleNamespace

from backend.app.model_gateway.embedding import EmbeddingProvider
from backend.app.services.exceptions import NotFoundError, ServiceError, ValidationError
import backend.app.services.embedding as embedding_module


@pytest.mark.asyncio
async def test_embedding_missing_document(service_context):
    session, _ = service_context
    with pytest.raises(NotFoundError):
        await EmbeddingService(session).embed_chunks(uuid4(), uuid4())


class _Repo:
    def __init__(self, value=None): self.value = value
    async def get_by_id(self, _id): return self.value
    async def list_by_document_id(self, _id): return self.value or []


@pytest.mark.asyncio
async def test_embedding_validation_matrix():
    service = EmbeddingService.__new__(EmbeddingService)
    document_id, config_id = uuid4(), uuid4()
    service.documents = _Repo(SimpleNamespace(id=document_id))
    service.chunks = _Repo([SimpleNamespace(id=uuid4(), document_id=document_id, chunk_index=0, content="x")])
    service.configs = _Repo(None)
    with pytest.raises(NotFoundError): await service.embed_chunks(document_id, config_id)
    service.configs = _Repo(SimpleNamespace(id=config_id, provider_id=uuid4(), model_type="chat", status="active"))
    with pytest.raises(ValidationError): await service.embed_chunks(document_id, config_id)


@pytest.mark.asyncio
async def test_embedding_multi_chunk_order_and_provider_shape_errors(monkeypatch):
    service = EmbeddingService.__new__(EmbeddingService)
    document_id, config_id, provider_id = uuid4(), uuid4(), uuid4()
    chunks = [SimpleNamespace(id=uuid4(), document_id=document_id, chunk_index=i, content=str(i)) for i in (2, 0, 1)]
    chunks.sort(key=lambda c: c.chunk_index)
    service.documents = _Repo(SimpleNamespace(id=document_id))
    service.chunks = _Repo(chunks)
    service.configs = _Repo(SimpleNamespace(provider_id=provider_id, model_type="embedding", status="active"))
    service.providers = _Repo(SimpleNamespace(provider_type="fake", status="active"))
    result = await service.embed_chunks(document_id, config_id)
    assert len(result) == len(chunks)
    assert [item.chunk_index for item in result] == [0, 1, 2]

    class BadProvider:
        def embed_texts(self, texts): return [[1.0]]
    monkeypatch.setattr(embedding_module, "embedding_provider_for", lambda _: BadProvider())
    with pytest.raises(ServiceError): await service.embed_chunks(document_id, config_id)

    class WrongDimension:
        def embed_texts(self, texts): return [[1.0], [1.0, 2.0], [1.0]]
    monkeypatch.setattr(embedding_module, "embedding_provider_for", lambda _: WrongDimension())
    with pytest.raises(ServiceError): await service.embed_chunks(document_id, config_id)


@pytest.mark.asyncio
async def test_embedding_no_chunks_returns_empty(service_context):
    session, _ = service_context
    service = EmbeddingService.__new__(EmbeddingService)
    document_id = uuid4()
    service.documents = _Repo(SimpleNamespace(id=document_id))
    service.chunks = _Repo([])
    result = await service.embed_chunks(document_id, uuid4())
    assert result == []
