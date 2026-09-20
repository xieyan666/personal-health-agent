"""Admin-only aggregated health analytics endpoint."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import require_role
from backend.app.core.database import get_db
from backend.app.schemas.admin_analytics import HealthAnalyticsSummary
from backend.app.services.admin_analytics_service import HealthAnalyticsService

router = APIRouter(prefix="/health-analytics", tags=["admin-health-analytics"])


@router.get(
    "/summary",
    response_model=HealthAnalyticsSummary,
    dependencies=[Depends(require_role("admin", "company_admin", "system_admin"))],
)
async def health_analytics_summary(
    period: str = Query(default="30d", pattern="^(7d|30d|90d)$"),
    department: str | None = Query(default=None, max_length=120),
    session: AsyncSession = Depends(get_db),
):
    """Anonymous aggregate health analytics. Employees may not call this."""
    return await HealthAnalyticsService(session).summary(period=period, department=department)
