"""Initial P0 schema.

Revision ID: 20260817_0001
Revises:
Create Date: 2026-08-17
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260817_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("auth_source", sa.String(length=40), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("auth_source", "external_user_id", name="uq_users_auth_source_external_user_id"),
    )
    op.create_index(op.f("ix_users_auth_source"), "users", ["auth_source"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_index(op.f("ix_users_status"), "users", ["status"], unique=False)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "model_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("provider_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=True),
        sa.Column("secret_ref", sa.String(length=255), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_model_providers_provider_type"), "model_providers", ["provider_type"], unique=False)
    op.create_index(op.f("ix_model_providers_status"), "model_providers", ["status"], unique=False)

    op.create_table(
        "model_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["provider_id"], ["model_providers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_model_configs_model_name"), "model_configs", ["model_name"], unique=False)
    op.create_index(op.f("ix_model_configs_model_type"), "model_configs", ["model_type"], unique=False)
    op.create_index(op.f("ix_model_configs_provider_id"), "model_configs", ["provider_id"], unique=False)
    op.create_index(op.f("ix_model_configs_status"), "model_configs", ["status"], unique=False)

    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("model_config_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("scope IN ('system', 'personal')", name="ck_agents_scope"),
        sa.CheckConstraint("scope = 'system' OR owner_user_id IS NOT NULL", name="ck_agents_personal_owner_required"),
        sa.CheckConstraint("version >= 1", name="ck_agents_version_positive"),
        sa.ForeignKeyConstraint(["model_config_id"], ["model_configs.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    for column in ("category", "model_config_id", "owner_user_id", "scope", "status"):
        op.create_index(op.f(f"ix_agents_{column}"), "agents", [column], unique=False)

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("agent_id", "last_message_at", "status", "user_id"):
        op.create_index(op.f(f"ix_conversations_{column}"), "conversations", [column], unique=False)
    op.create_index("ix_conversations_user_updated_at", "conversations", ["user_id", "updated_at"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=True),
        sa.Column("source_reference", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("safety_status", sa.String(length=20), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["parent_message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("parent_message_id", "risk_level", "role", "safety_status", "source_type", "status"):
        op.create_index(op.f(f"ix_messages_{column}"), "messages", [column], unique=False)
    op.create_index("ix_messages_conversation_created_at", "messages", ["conversation_id", "created_at"], unique=False)

    op.create_table(
        "knowledge_bases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("embedding_model_config_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("vector_collection", sa.String(length=255), nullable=True),
        sa.Column("index_version", sa.Integer(), nullable=False),
        sa.Column("retrieval_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("index_version >= 1", name="ck_knowledge_bases_index_version_positive"),
        sa.ForeignKeyConstraint(["embedding_model_config_id"], ["model_configs.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "name", name="uq_knowledge_bases_owner_name"),
    )
    for column in ("embedding_model_config_id", "owner_user_id", "status", "vector_collection"):
        op.create_index(op.f(f"ix_knowledge_bases_{column}"), "knowledge_bases", [column], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_reference", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("mime_type", sa.String(length=127), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("content_hash", "knowledge_base_id", "source_type", "status"):
        op.create_index(op.f(f"ix_documents_{column}"), "documents", [column], unique=False)

    op.create_table(
        "tools",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("tool_type", sa.String(length=40), nullable=False),
        sa.Column("implementation_ref", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("input_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("secret_ref", sa.String(length=255), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    for column in ("requires_approval", "risk_level", "status", "tool_type"):
        op.create_index(op.f(f"ix_tools_{column}"), "tools", [column], unique=False)

    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trigger_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("output_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_config_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("safety_status", sa.String(length=20), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("completion_tokens >= 0", name="ck_agent_runs_completion_tokens"),
        sa.CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_agent_runs_latency_ms"),
        sa.CheckConstraint("prompt_tokens >= 0", name="ck_agent_runs_prompt_tokens"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["model_config_id"], ["model_configs.id"]),
        sa.ForeignKeyConstraint(["output_message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["parent_run_id"], ["agent_runs.id"]),
        sa.ForeignKeyConstraint(["trigger_message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("agent_id", "conversation_id", "error_code", "model_config_id", "output_message_id", "parent_run_id", "risk_level", "safety_status", "started_at", "status", "trace_id", "trigger_message_id", "user_id"):
        op.create_index(op.f(f"ix_agent_runs_{column}"), "agent_runs", [column], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=60), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("safety_status", sa.String(length=20), nullable=True),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("action", "actor_user_id", "agent_run_id", "outcome", "request_id", "risk_level", "safety_status", "trace_id"):
        op.create_index(op.f(f"ix_audit_logs_{column}"), "audit_logs", [column], unique=False)
    op.create_index("ix_audit_logs_created_at_id", "audit_logs", ["created_at", "id"], unique=False)
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("agent_runs")
    op.drop_table("tools")
    op.drop_table("documents")
    op.drop_table("knowledge_bases")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("agents")
    op.drop_table("model_configs")
    op.drop_table("model_providers")
    op.drop_table("users")
