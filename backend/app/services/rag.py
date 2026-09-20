"""RAG context assembly without answer generation."""

from dataclasses import dataclass
from uuid import UUID

from backend.app.services.retrieval import RetrievalResult, RetrievalService


@dataclass(frozen=True)
class RagContext:
    query: str
    knowledge_base_id: UUID
    chunks: list[RetrievalResult]
    context_text: str


class RagService:
    def __init__(self, session, retrieval: RetrievalService | None = None) -> None:
        self.retrieval = retrieval or RetrievalService(session)

    async def build_context(self, knowledge_base_id: UUID, query: str, model_config_id: UUID, top_k: int = 5) -> RagContext:
        chunks = await self.retrieval.retrieve(knowledge_base_id, query, model_config_id, top_k)
        context = "\n\n".join(f"--- chunk {chunk.chunk_index} ---\n{chunk.content}" for chunk in chunks)
        return RagContext(query, knowledge_base_id, chunks, context)
