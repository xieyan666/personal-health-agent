from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1)
    model_config_id: UUID
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievalChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    score: float


class RagContextResponse(BaseModel):
    query: str
    knowledge_base_id: UUID
    chunks: list[RetrievalChunkResponse]
    context_text: str
