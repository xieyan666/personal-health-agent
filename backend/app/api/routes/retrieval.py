from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.schemas.retrieval import RagContextResponse, RetrievalChunkResponse, RetrievalRequest
from backend.app.services.rag import RagService
from backend.app.services.retrieval import RetrievalService

router = APIRouter(tags=["retrieval"])


@router.post("/knowledge-bases/{knowledge_base_id}/retrieve", response_model=list[RetrievalChunkResponse])
async def retrieve(knowledge_base_id: UUID, request: RetrievalRequest, session: AsyncSession = Depends(get_db)):
    return await RetrievalService(session).retrieve(knowledge_base_id, request.query, request.model_config_id, request.top_k)


@router.post("/knowledge-bases/{knowledge_base_id}/rag-context", response_model=RagContextResponse)
async def rag_context(knowledge_base_id: UUID, request: RetrievalRequest, session: AsyncSession = Depends(get_db)):
    return await RagService(session).build_context(knowledge_base_id, request.query, request.model_config_id, request.top_k)
