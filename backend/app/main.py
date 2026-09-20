"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.errors import register_service_exception_handlers
from backend.app.api.routes import (
    agent_runs_router,
    agents_router,
    conversations_router,
    documents_router,
    chunks_router,
    messages_router,
    model_configs_router,
    model_providers_router,
    users_router,
    retrieval_router,
    agent_runtime_router,
    auth_router,
    health_agent_router,
    health_profile_router,
    health_data_router,
    health_risk_router,
    health_summary_router,
    health_reports_router,
)
from backend.app.api.routes.health_risk_trend import router as health_risk_trend_router
from backend.app.api.routes.rbac_users import router as rbac_users_router
from backend.app.api.routes.health_plans import router as health_plans_router
from backend.app.api.routes.health_services import router as health_services_router
from backend.app.api.routes.mental_health import router as mental_health_router
from backend.app.api.routes.notifications import router as notifications_router
from backend.app.api.routes.user_profile import router as user_profile_router
from backend.app.api.routes.admin_analytics import router as admin_analytics_router
from backend.app.api.routes.admin_health_activities import router as admin_health_activities_router
from backend.app.api.routes.risk_cases import router as admin_risk_cases_router
from backend.app.api.routes.checkups import router as admin_checkups_router
from backend.app.api.routes.data_authorizations import router as data_authorizations_router
from backend.app.api.routes.dashboard import router as dashboard_router
from backend.app.api.routes.admin_knowledge import router as admin_knowledge_router
from backend.app.api.routes.admin_models import router as admin_models_router
from backend.app.api.routes.admin_agents import router as admin_agents_router
from backend.app.api.routes.admin_system_monitor import router as admin_system_monitor_router
from backend.app.middleware.request_metrics import RequestMetricsMiddleware


app = FastAPI(title="Personal Health Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5341", "http://127.0.0.1:5341", "app://.",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestMetricsMiddleware)
register_service_exception_handlers(app)
app.include_router(users_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(model_providers_router, prefix="/api/v1")
app.include_router(model_configs_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(messages_router, prefix="/api/v1")
app.include_router(agent_runs_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(chunks_router, prefix="/api/v1")
app.include_router(retrieval_router, prefix="/api/v1")
app.include_router(agent_runtime_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(health_agent_router, prefix="/api/v1")
app.include_router(health_profile_router, prefix="/api/v1")
app.include_router(health_data_router, prefix="/api/v1")
app.include_router(health_risk_router, prefix="/api/v1")
app.include_router(health_summary_router, prefix="/api/v1")
app.include_router(health_reports_router, prefix="/api/v1")
app.include_router(health_plans_router, prefix="/api/v1")
app.include_router(health_services_router, prefix="/api/v1")
app.include_router(mental_health_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(user_profile_router, prefix="/api/v1")
app.include_router(data_authorizations_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(health_risk_trend_router, prefix="/api/v1")
app.include_router(rbac_users_router, prefix="/api/v1/admin")
app.include_router(admin_analytics_router, prefix="/api/v1/admin")
app.include_router(admin_risk_cases_router, prefix="/api/v1/admin")
app.include_router(admin_checkups_router, prefix="/api/v1/admin")
app.include_router(admin_health_activities_router, prefix="/api/v1/admin")
app.include_router(admin_models_router, prefix="/api/v1/admin")
app.include_router(admin_agents_router, prefix="/api/v1")
app.include_router(admin_knowledge_router, prefix="/api/v1")
app.include_router(admin_system_monitor_router, prefix="/api/v1/admin")
app.include_router(rbac_users_router, prefix="/api")


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
