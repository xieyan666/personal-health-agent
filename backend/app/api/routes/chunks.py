from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_db
from backend.app.schemas import ChunkResponse
from backend.app.services.chunk import ChunkService

router = APIRouter(tags=["chunks"])


@router.get("/documents/{document_id}/chunks", response_model=List[ChunkResponse])
async def list_chunks(
    document_id: UUID, session: AsyncSession = Depends(get_db)
) -> List[ChunkResponse]:
    return await ChunkService(session).list_chunks(document_id)
