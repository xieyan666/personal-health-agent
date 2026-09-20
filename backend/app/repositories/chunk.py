"""Document chunk data access."""

from __future__ import annotations

from typing import List, Sequence
from uuid import UUID

from sqlalchemy import delete, select

from backend.app.models import DocumentChunk
from backend.app.repositories.base import BaseRepository


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    model = DocumentChunk

    async def list_by_document_id(
        self, document_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[DocumentChunk]:
        return await self._list(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc()),
            offset,
            limit,
        )

    async def exists_by_document_and_index(
        self, document_id: UUID, chunk_index: int
    ) -> bool:
        result = await self.session.execute(
            select(DocumentChunk.id)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.chunk_index == chunk_index,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def exists_by_document_id(self, document_id: UUID) -> bool:
        result = await self.session.execute(
            select(DocumentChunk.id).where(DocumentChunk.document_id == document_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_by_ids(self, chunk_ids: Sequence[UUID]) -> List[DocumentChunk]:
        if not chunk_ids:
            return []
        result = await self.session.execute(
            select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
        )
        return list(result.scalars().all())

    async def delete_by_document_id(self, document_id: UUID) -> int:
        result = await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        await self.session.flush()
        return int(result.rowcount or 0)
