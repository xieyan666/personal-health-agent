"""Request-scoped API dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.services import (
    AgentRunService,
    AgentService,
    ConversationService,
    DocumentIngestionService,
    MessageService,
    ModelConfigService,
    ModelProviderService,
    UserService,
)


def get_document_ingestion_service(
    session: AsyncSession = Depends(get_db),
) -> DocumentIngestionService:
    return DocumentIngestionService(session)


def get_agent_run_service(
    session: AsyncSession = Depends(get_db),
) -> AgentRunService:
    return AgentRunService(session)


def get_user_service(
    session: AsyncSession = Depends(get_db),
) -> UserService:
    return UserService(session)


def get_agent_service(
    session: AsyncSession = Depends(get_db),
) -> AgentService:
    return AgentService(session)


def get_model_provider_service(
    session: AsyncSession = Depends(get_db),
) -> ModelProviderService:
    return ModelProviderService(session)


def get_model_config_service(
    session: AsyncSession = Depends(get_db),
) -> ModelConfigService:
    return ModelConfigService(session)


def get_conversation_service(
    session: AsyncSession = Depends(get_db),
) -> ConversationService:
    return ConversationService(session)


def get_message_service(
    session: AsyncSession = Depends(get_db),
) -> MessageService:
    return MessageService(session)
