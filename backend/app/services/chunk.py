"""Chunk generation and read/delete orchestration."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.repositories import DocumentChunkRepository, DocumentRepository
from backend.app.services.base import BaseService
from backend.app.services.exceptions import ConflictError, NotFoundError
from backend.app.services.text_chunker import split_text


class ChunkService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.documents = DocumentRepository(session)
        self.chunks = DocumentChunkRepository(session)

    async def create_chunks(self, document_id: UUID, text: str):
        if await self.documents.get_by_id(document_id) is None:
            raise NotFoundError(f"Document not found: {document_id}")
        if await self.chunks.exists_by_document_id(document_id):
            raise ConflictError(f"Document already has chunks: {document_id}")
        contents = split_text(text)
        if not contents:
            return []
        async with self._transaction():
            for index, content in enumerate(contents):
                await self.chunks.create(
                    document_id=document_id,
                    chunk_index=index,
                    content=content,
                    char_count=len(content),
                )
        return await self.chunks.list_by_document_id(document_id)

    async def list_chunks(self, document_id: UUID):
        if await self.documents.get_by_id(document_id) is None:
            raise NotFoundError(f"Document not found: {document_id}")
        return await self.chunks.list_by_document_id(document_id)

    async def delete_chunks(self, document_id: UUID) -> int:
        if await self.documents.get_by_id(document_id) is None:
            raise NotFoundError(f"Document not found: {document_id}")
        async with self._transaction():
            return await self.chunks.delete_by_document_id(document_id)
