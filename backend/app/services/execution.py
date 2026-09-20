"""Agent run metadata business operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import AgentRun
from backend.app.repositories import (
    AgentRepository,
    AgentRunRepository,
    AuditLogRepository,
    ConversationRepository,
    MessageRepository,
    ModelConfigRepository,
    UserRepository,
)
from backend.app.services.base import BaseService
from backend.app.services.exceptions import ConflictError, NotFoundError, ValidationError


class AgentRunService(BaseService):
    VALID_STATUSES = {"pending", "running", "succeeded", "failed", "cancelled"}
    STATUS_TRANSITIONS = {
        "pending": {"running", "cancelled"},
        "running": {"succeeded", "failed", "cancelled"},
        "succeeded": set(),
        "failed": set(),
        "cancelled": set(),
    }
    TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repository = AgentRunRepository(session)
        self.users = UserRepository(session)
        self.agents = AgentRepository(session)
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)
        self.model_configs = ModelConfigRepository(session)
        self.audit_logs = AuditLogRepository(session)

    async def get_agent_run(self, run_id: UUID) -> AgentRun:
        run = await self.repository.get_by_id(run_id)
        if run is None:
            raise NotFoundError(f"Agent run not found: {run_id}")
        return run

    async def list_agent_runs(
        self,
        offset: int = 0,
        limit: int = 100,
        agent_id: Optional[UUID] = None,
        conversation_id: Optional[UUID] = None,
        parent_run_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> List[AgentRun]:
        self._validate_status(status)
        return await self.repository.list_filtered(
            offset=offset,
            limit=limit,
            agent_id=agent_id,
            conversation_id=conversation_id,
            parent_run_id=parent_run_id,
            status=status,
        )

    async def create_agent_run(self, **values: Any) -> AgentRun:
        async with self._transaction():
            user_id = values["user_id"]
            agent_id = values["agent_id"]
            conversation_id = values["conversation_id"]
            self._validate_status(values.get("status"))
            self._validate_non_negative(values)

            if await self.users.get_by_id(user_id) is None:
                raise NotFoundError(f"User not found: {user_id}")
            if await self.agents.get_by_id(agent_id) is None:
                raise NotFoundError(f"Agent not found: {agent_id}")
            conversation = await self.conversations.get_by_id(conversation_id)
            if conversation is None:
                raise NotFoundError(f"Conversation not found: {conversation_id}")
            if conversation.agent_id != agent_id:
                raise ValidationError("Conversation belongs to another agent")
            if conversation.user_id != user_id:
                raise ValidationError("Conversation belongs to another user")

            await self._validate_message(
                values.get("trigger_message_id"), conversation_id, "trigger_message_id"
            )
            await self._validate_parent(values.get("parent_run_id"), conversation_id)
            await self._validate_model_config(values.get("model_config_id"))
            return await self.repository.create(**values)

    async def create_child_agent_run(
        self,
        *,
        user_id: UUID,
        child_agent_id: UUID,
        conversation_id: UUID,
        parent_run_id: UUID,
        root_agent_id: UUID,
        model_config_id: Optional[UUID],
        input_summary: Optional[str],
        risk_level: str,
        safety_status: str,
    ) -> AgentRun:
        """Create an internal Multi-Agent child run for the root conversation.

        A child run deliberately records the executing child agent while retaining
        the coordinator conversation; this exception is not exposed by public APIs.
        """
        async with self._transaction():
            conversation = await self.conversations.get_by_id(conversation_id)
            if conversation is None:
                raise NotFoundError(f"Conversation not found: {conversation_id}")
            if conversation.user_id != user_id or conversation.agent_id != root_agent_id:
                raise ValidationError("MULTI_AGENT_INTERNAL_RUN_BLOCKER")
            parent = await self.repository.get_by_id(parent_run_id)
            if parent is None or parent.conversation_id != conversation_id:
                raise ValidationError("MULTI_AGENT_INTERNAL_RUN_BLOCKER")
            coordinator = await self.agents.get_by_id(parent.agent_id)
            child = await self.agents.get_by_id(child_agent_id)
            if coordinator is None or child is None:
                raise NotFoundError("SUB_AGENT_NOT_FOUND")
            if child.status != "active":
                raise ValidationError("SUB_AGENT_INACTIVE")
            config = coordinator.config if isinstance(coordinator.config, dict) else {}
            multi = config.get("multi_agent", {}) if isinstance(config.get("multi_agent", {}), dict) else {}
            authorized = {str(value) for value in multi.get("sub_agent_ids", []) if value is not None}
            if str(child_agent_id) not in authorized:
                raise ValidationError("SUB_AGENT_NOT_AUTHORIZED")
            await self._validate_model_config(model_config_id)
            return await self.repository.create(
                user_id=user_id,
                agent_id=child_agent_id,
                conversation_id=conversation_id,
                trigger_message_id=None,
                parent_run_id=parent_run_id,
                model_config_id=model_config_id,
                status="pending",
                input_summary=input_summary,
                risk_level=risk_level,
                safety_status=safety_status,
            )

    async def update_agent_run(self, run_id: UUID, **values: Any) -> AgentRun:
        async with self._transaction():
            run = await self.get_agent_run(run_id)
            self._validate_non_negative(values)
            if "output_message_id" in values:
                await self._validate_message(
                    values.get("output_message_id"),
                    run.conversation_id,
                    "output_message_id",
                )

            if "status" in values:
                new_status = values["status"]
                self._validate_status(new_status)
                if new_status != run.status:
                    allowed = self.STATUS_TRANSITIONS.get(run.status, set())
                    if new_status not in allowed:
                        raise ValidationError(
                            f"Invalid agent run status transition: {run.status} -> {new_status}"
                        )
                    now = datetime.now(timezone.utc)
                    if new_status == "running" and run.started_at is None:
                        values["started_at"] = now
                    if new_status in self.TERMINAL_STATUSES and run.finished_at is None:
                        values["finished_at"] = now

            updated = await self.repository.update(run, **values)
        await self.session.refresh(updated)
        return updated

    async def delete_agent_run(self, run_id: UUID) -> None:
        async with self._transaction():
            run = await self.get_agent_run(run_id)
            if await self.repository.exists_children(run_id):
                raise ConflictError("Agent run is referenced by child runs")
            if await self.audit_logs.exists_by_agent_run_id(run_id):
                raise ConflictError("Agent run is referenced by audit logs")
            await self.repository.delete(run)

    def _validate_status(self, status: Optional[str]) -> None:
        if status is not None and status not in self.VALID_STATUSES:
            raise ValidationError(f"Invalid agent run status: {status}")

    @staticmethod
    def _validate_non_negative(values: dict[str, Any]) -> None:
        for field in ("prompt_tokens", "completion_tokens", "latency_ms"):
            value = values.get(field)
            if value is not None and value < 0:
                raise ValidationError(f"{field} must be greater than or equal to 0")

    async def _validate_message(
        self, message_id: Optional[UUID], conversation_id: UUID, field: str
    ) -> None:
        if message_id is None:
            return
        message = await self.messages.get_by_id(message_id)
        if message is None:
            raise NotFoundError(f"Message not found: {message_id}")
        if message.conversation_id != conversation_id:
            raise ValidationError(f"{field} belongs to another conversation")

    async def _validate_parent(
        self, parent_run_id: Optional[UUID], conversation_id: UUID
    ) -> None:
        if parent_run_id is None:
            return
        parent = await self.repository.get_by_id(parent_run_id)
        if parent is None:
            raise NotFoundError(f"Parent agent run not found: {parent_run_id}")
        if parent.conversation_id != conversation_id:
            raise ValidationError("Parent agent run belongs to another conversation")

    async def _validate_model_config(self, model_config_id: Optional[UUID]) -> None:
        if model_config_id is not None and await self.model_configs.get_by_id(
            model_config_id
        ) is None:
            raise NotFoundError(f"Model config not found: {model_config_id}")
