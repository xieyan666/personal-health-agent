from uuid import UUID, uuid4
from typing import Optional
from sqlalchemy import String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.models.base import Base
class Department(Base):
    __tablename__ = "departments"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))
class Position(Base):
    __tablename__ = "positions"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    department_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("departments.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
