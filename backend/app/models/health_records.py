from __future__ import annotations
from datetime import date
from uuid import UUID, uuid4
from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.models.base import Base, TimestampMixin

class SleepRecord(TimestampMixin, Base):
    __tablename__ = "sleep_records"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    record_date: Mapped[date] = mapped_column("date", Date, index=True)
    sleep_duration: Mapped[float] = mapped_column(Float)
    deep_sleep_duration: Mapped[float] = mapped_column(Float)
    light_sleep_duration: Mapped[float] = mapped_column(Float)
    sleep_quality: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(40), default="Wearable")

class ExerciseRecord(TimestampMixin, Base):
    __tablename__ = "exercise_records"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    record_date: Mapped[date] = mapped_column("date", Date, index=True)
    exercise_duration: Mapped[int] = mapped_column(Integer)
    steps: Mapped[int] = mapped_column(Integer)
    calories: Mapped[int] = mapped_column(Integer)
    exercise_type: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(40), default="Wearable")

class HeartRateRecord(TimestampMixin, Base):
    __tablename__ = "heart_rate_records"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    record_date: Mapped[date] = mapped_column("date", Date, index=True)
    average_heart_rate: Mapped[int] = mapped_column(Integer)
    resting_heart_rate: Mapped[int] = mapped_column(Integer)
    max_heart_rate: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(40), default="Wearable")
