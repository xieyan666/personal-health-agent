"""Qdrant indexing for existing document chunks."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from qdrant_client import AsyncQdrantClient, models

from backend.app.core.qdrant import get_qdrant_client
from backend.app.repositories import DocumentRepository, KnowledgeBaseRepository
from backend.app.services.embedding import EmbeddingService
from backend.app.services.exceptions import NotFoundError, ServiceError, ValidationError


@dataclass(frozen=True)
class DocumentIndexResult:
    document_id: UUID
    knowledge_base_id: UUID
    collection_name: str
    indexed_count: int
    dimension: int


class QdrantIndexService:
    def __init__(self, session, client: AsyncQdrantClient | None = None) -> None:
        self.documents = DocumentRepository(session)
        self.knowledge_bases = KnowledgeBaseRepository(session)
        self.embedding = EmbeddingService(session)
        self.client = client or get_qdrant_client()

    async def index_document(self, document_id: UUID, model_config_id: UUID) -> DocumentIndexResult:
        document = await self.documents.get_by_id(document_id)
        if document is None:
            raise NotFoundError(f"Document not found: {document_id}")
        knowledge_base = await self.knowledge_bases.get_by_id(document.knowledge_base_id)
        if knowledge_base is None:
            raise NotFoundError(f"Knowledge base not found: {document.knowledge_base_id}")
        if not knowledge_base.vector_collection:
            raise ValidationError("Knowledge base vector_collection is required")
        embeddings = await self.embedding.embed_chunks(document_id, model_config_id)
        if not embeddings:
            return DocumentIndexResult(document_id, knowledge_base.id, knowledge_base.vector_collection, 0, 0)
        dimensions = {item.dimension for item in embeddings}
        if len(dimensions) != 1:
            raise ServiceError("Embedding dimensions are inconsistent")
        dimension = dimensions.pop()
        collection = knowledge_base.vector_collection
        try:
            if not await self.client.collection_exists(collection):
                await self.client.create_collection(
                    collection_name=collection,
                    vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
                )
            else:
                info = await self.client.get_collection(collection)
                vectors = info.config.params.vectors
                actual_size = vectors.size if isinstance(vectors, models.VectorParams) else None
                if actual_size != dimension:
                    raise ServiceError("Qdrant collection vector size does not match embeddings")
            points = [
                models.PointStruct(
                    id=str(item.chunk_id), vector=item.vector,
                    payload={
                        "chunk_id": str(item.chunk_id), "document_id": str(item.document_id),
                        "knowledge_base_id": str(knowledge_base.id), "chunk_index": item.chunk_index,
                        "document_name": document.name,
                    },
                ) for item in embeddings
            ]
            await self.client.upsert(collection_name=collection, points=points, wait=True)
            stored = await self.client.retrieve(collection_name=collection, ids=[str(item.chunk_id) for item in embeddings], with_payload=False)
        except ServiceError:
            raise
        except Exception as exc:
            raise ServiceError("Qdrant indexing failed") from exc
        if len(stored) != len(points):
            raise ServiceError("Qdrant upsert count does not match embeddings")
        return DocumentIndexResult(document_id, knowledge_base.id, collection, len(points), dimension)

    async def delete_document_index(self, document_id: UUID) -> int:
        document = await self.documents.get_by_id(document_id)
        if document is None:
            raise NotFoundError(f"Document not found: {document_id}")
        knowledge_base = await self.knowledge_bases.get_by_id(document.knowledge_base_id)
        if knowledge_base is None:
            raise NotFoundError(f"Knowledge base not found: {document.knowledge_base_id}")
        if not knowledge_base.vector_collection:
            raise ValidationError("Knowledge base vector_collection is required")
        try:
            if not await self.client.collection_exists(knowledge_base.vector_collection):
                return 0
            selector = models.FilterSelector(filter=models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=str(document_id)))]))
            await self.client.delete(collection_name=knowledge_base.vector_collection, points_selector=selector, wait=True)
        except Exception as exc:
            raise ServiceError("Qdrant index deletion failed") from exc
        return 0
