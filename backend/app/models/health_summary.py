from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.models.base import Base, TimestampMixin
class HealthSummary(TimestampMixin, Base):
    __tablename__='health_summaries'
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True, nullable=False)
    period: Mapped[str] = mapped_column(String(30), nullable=False, default='30days')
    summary_content: Mapped[dict] = mapped_column(JSONB, nullable=False)
