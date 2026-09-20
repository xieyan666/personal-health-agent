from uuid import UUID, uuid4
from datetime import date
from typing import Optional
from sqlalchemy import String, ForeignKey, Date, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.models.base import Base, TimestampMixin

class Company(TimestampMixin, Base):
    __tablename__ = "companies"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)

class Employee(TimestampMixin, Base):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("company_id", "employee_no", name="uq_employees_company_no"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    company_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    employee_no: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    join_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

class Role(TimestampMixin, Base):
    __tablename__ = "roles"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

class RolePermission(Base):
    __tablename__ = "role_permissions"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    role_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    permission_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("permissions.id"), nullable=False)
