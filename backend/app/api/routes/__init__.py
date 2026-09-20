"""Versioned API routers."""

from backend.app.api.routes.agents import router as agents_router
from backend.app.api.routes.agent_runs import router as agent_runs_router
from backend.app.api.routes.conversations import router as conversations_router
from backend.app.api.routes.documents import router as documents_router
from backend.app.api.routes.chunks import router as chunks_router
from backend.app.api.routes.messages import router as messages_router
from backend.app.api.routes.model_configs import router as model_configs_router
from backend.app.api.routes.model_providers import router as model_providers_router
from backend.app.api.routes.users import router as users_router
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.retrieval import router as retrieval_router
from backend.app.api.routes.agent_runtime import router as agent_runtime_router
from backend.app.api.routes.health_agent import router as health_agent_router
from backend.app.api.routes.health_profile import router as health_profile_router
from backend.app.api.routes.health_data import router as health_data_router
from backend.app.api.routes.health_risk import router as health_risk_router
from backend.app.api.routes.health_summary import router as health_summary_router
from backend.app.api.routes.health_reports import router as health_reports_router
from backend.app.api.routes.admin_health_activities import router as admin_health_activities_router
from backend.app.api.routes.admin_agents import router as admin_agents_router

__all__ = [
    "agents_router",
    "agent_runs_router",
    "conversations_router",
    "documents_router",
    "chunks_router",
    "messages_router",
    "model_configs_router",
    "model_providers_router",
    "users_router",
    "auth_router",
    "retrieval_router",
    "agent_runtime_router",
    "health_agent_router",
    "health_profile_router",
    "health_data_router",
    "health_risk_router",
    "health_summary_router",
    "health_reports_router",
    "admin_health_activities_router",
    "admin_agents_router",
]
