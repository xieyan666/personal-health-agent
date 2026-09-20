"""Knowledge base and document persistence models."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin


class KnowledgeBase(TimestampMixin, Base):
    """A user-owned knowledge base backed by a Qdrant collection."""

    __tablename__ = "knowledge_bases"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id", "name", name="uq_knowledge_bases_owner_name"
        ),
        CheckConstraint(
            "index_version >= 1", name="ck_knowledge_bases_index_version_positive"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    embedding_model_config_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("model_configs.id"), nullable=True, index=True
    )
    vector_collection: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    index_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retrieval_config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    owner: Mapped["User"] = relationship()
    embedding_model_config: Mapped[Optional["ModelConfig"]] = relationship()
    documents: Mapped[List["Document"]] = relationship(back_populates="knowledge_base")


class Document(TimestampMixin, Base):
    """Document metadata whose owner is derived through its knowledge base."""

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    knowledge_base_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_bases.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_reference: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    mime_type: Mapped[Optional[str]] = mapped_column(String(127), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    knowledge_base: Mapped[KnowledgeBase] = relationship(back_populates="documents")
    chunks: Mapped[List["DocumentChunk"]] = relationship(back_populates="document")
