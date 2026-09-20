"""In-memory Chunk embedding orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.model_gateway.embedding import embedding_provider_for
from backend.app.repositories import (
    DocumentChunkRepository,
    DocumentRepository,
    ModelConfigRepository,
    ModelProviderRepository,
)
from backend.app.services.exceptions import NotFoundError, ServiceError, ValidationError


@dataclass(frozen=True)
class ChunkEmbedding:
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    vector: list[float]
    dimension: int


class EmbeddingService:
    def __init__(self, session: AsyncSession) -> None:
        self.documents = DocumentRepository(session)
        self.chunks = DocumentChunkRepository(session)
        self.configs = ModelConfigRepository(session)
        self.providers = ModelProviderRepository(session)

    async def embed_chunks(self, document_id: UUID, model_config_id: UUID) -> list[ChunkEmbedding]:
        if await self.documents.get_by_id(document_id) is None:
            raise NotFoundError(f"Document not found: {document_id}")
        chunks = await self.chunks.list_by_document_id(document_id)
        if not chunks:
            return []
        config = await self.configs.get_by_id(model_config_id)
        if config is None:
            raise NotFoundError(f"Model config not found: {model_config_id}")
        if config.model_type != "embedding":
            raise ValidationError("Model config is not an embedding model")
        provider = await self.providers.get_by_id(config.provider_id)
        if provider is None:
            raise NotFoundError(f"Model provider not found: {config.provider_id}")
        if provider.status != "active" or config.status != "active":
            raise ValidationError("Embedding provider and config must be active")
        vectors = embedding_provider_for(provider.provider_type).embed_texts([c.content for c in chunks])
        if len(vectors) != len(chunks):
            raise ServiceError("Embedding provider returned an invalid vector count")
        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1 or not dimensions or any(
            not isinstance(value, (float, int)) for vector in vectors for value in vector
        ):
            raise ServiceError("Embedding provider returned invalid vector dimensions")
        dimension = dimensions.pop()
        return [
            ChunkEmbedding(c.id, c.document_id, c.chunk_index, [float(v) for v in vector], dimension)
            for c, vector in zip(chunks, vectors)
        ]

    async def embed_query(self, query: str, model_config_id: UUID) -> list[float]:
        config = await self.configs.get_by_id(model_config_id)
        if config is None:
            raise NotFoundError(f"Model config not found: {model_config_id}")
        if config.model_type != "embedding":
            raise ValidationError("Model config is not an embedding model")
        provider = await self.providers.get_by_id(config.provider_id)
        if provider is None:
            raise NotFoundError(f"Model provider not found: {config.provider_id}")
        if provider.status != "active" or config.status != "active":
            raise ValidationError("Embedding provider and config must be active")
        vectors = embedding_provider_for(provider.provider_type).embed_texts([query])
        if len(vectors) != 1 or not vectors[0] or any(
            not isinstance(value, (float, int)) for value in vectors[0]
        ):
            raise ServiceError("Embedding provider returned an invalid query vector")
        return [float(value) for value in vectors[0]]
