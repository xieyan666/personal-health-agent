"""Knowledge base and document metadata data access."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select

from backend.app.models import Document, KnowledgeBase
from backend.app.repositories.base import BaseRepository


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    model = KnowledgeBase

    async def get_by_owner_and_name(
        self, owner_user_id: UUID, name: str
    ) -> Optional[KnowledgeBase]:
        result = await self.session.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.owner_user_id == owner_user_id,
                KnowledgeBase.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_owner_user_id(
        self, owner_user_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[KnowledgeBase]:
        return await self._list(
            select(KnowledgeBase).where(
                KnowledgeBase.owner_user_id == owner_user_id
            ),
            offset,
            limit,
        )


class DocumentRepository(BaseRepository[Document]):
    model = Document

    async def list_by_knowledge_base_id(
        self, knowledge_base_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[Document]:
        return await self._list(
            select(Document).where(
                Document.knowledge_base_id == knowledge_base_id
            ),
            offset,
            limit,
        )
