"""Knowledge-base-scoped vector retrieval with PostgreSQL content hydration."""

from dataclasses import dataclass
from uuid import UUID

from qdrant_client import AsyncQdrantClient, models

from backend.app.core.qdrant import get_qdrant_client
from backend.app.repositories import DocumentChunkRepository, KnowledgeBaseRepository
from backend.app.services.embedding import EmbeddingService
from backend.app.services.exceptions import NotFoundError, ServiceError, ValidationError


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    score: float


class RetrievalService:
    def __init__(self, session, client: AsyncQdrantClient | None = None) -> None:
        self.knowledge_bases = KnowledgeBaseRepository(session)
        self.chunks = DocumentChunkRepository(session)
        self.embedding = EmbeddingService(session)
        self.client = client or get_qdrant_client()

    async def retrieve(self, knowledge_base_id: UUID, query: str, model_config_id: UUID, top_k: int = 5) -> list[RetrievalResult]:
        if not query or not query.strip():
            raise ValidationError("Query must not be empty")
        if top_k < 1 or top_k > 20:
            raise ValidationError("top_k must be between 1 and 20")
        knowledge_base = await self.knowledge_bases.get_by_id(knowledge_base_id)
        if knowledge_base is None:
            raise NotFoundError(f"Knowledge base not found: {knowledge_base_id}")
        if not knowledge_base.vector_collection or not await self.client.collection_exists(knowledge_base.vector_collection):
            return []
        vector = await self.embedding.embed_query(query, model_config_id)
        try:
            response = await self.client.query_points(
                collection_name=knowledge_base.vector_collection,
                query=vector,
                limit=top_k,
                with_payload=True,
            )
        except Exception as exc:
            raise ServiceError("Qdrant retrieval failed") from exc
        ordered: list[tuple[UUID, float]] = []
        for point in response.points:
            payload = point.payload or {}
            if payload.get("knowledge_base_id") != str(knowledge_base_id):
                continue
            try:
                ordered.append((UUID(str(payload["chunk_id"])), float(point.score)))
            except (KeyError, TypeError, ValueError):
                continue
        hydrated = {chunk.id: chunk for chunk in await self.chunks.list_by_ids([item[0] for item in ordered])}
        return [
            RetrievalResult(chunk_id, chunk.document_id, chunk.chunk_index, chunk.content, score)
            for chunk_id, score in ordered
            if (chunk := hydrated.get(chunk_id)) is not None
        ]
