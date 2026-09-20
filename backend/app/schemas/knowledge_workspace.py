"""Admin knowledge-base workspace request/response contracts."""
from __future__ import annotations
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    domain: str = Field(default="通用健康知识", max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    enabled: bool = True
    agent_ids: list[UUID] = Field(default_factory=list)


class KnowledgeBaseAgentsUpdate(BaseModel):
    agent_ids: list[UUID] = Field(default_factory=list)


class RetrievalTestRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)


class KnowledgeBaseSummary(BaseModel):
    id: UUID
    name: str
    domain: str
    description: str | None
    status: str
    document_count: int
    chunk_count: int
    vector_progress: int
    updated_at: str
    agents: list[dict[str, Any]] = Field(default_factory=list)
