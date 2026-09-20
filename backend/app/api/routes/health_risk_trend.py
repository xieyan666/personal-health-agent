from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import get_current_user
from backend.app.core.database import get_db
from backend.app.models import HealthRiskScore
from backend.app.services.health_risk_trend import build_weekly_risk_scores

router = APIRouter(prefix="/health-risk", tags=["health-risk"])


@router.get("/trend")
async def trend(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    rows = await build_weekly_risk_scores(session, current_user.id)
    return {
        "period": "last_30_days",
        "dimension": "weekly",
        "data": [
            {
                "period": "本周" if index == 4 else f"第{index + 1}周",
                "start_date": row.period_start.isoformat(),
                "end_date": row.period_end.isoformat(),
                "score": row.risk_score,
                "level": row.risk_level,
                "factors": row.main_factors,
            }
            for index, row in enumerate(rows)
        ],
    }


@router.get("/history")
async def history(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    """Return persisted, rules-only assessment periods for the current user.

    `health_risk_scores` is the source of truth for phase assessments.  A first
    visit creates the current five assessment periods; later reads never ask an
    LLM to infer scores or levels.
    """
    rows = list(
        (
            await session.scalars(
                select(HealthRiskScore)
                .where(HealthRiskScore.user_id == current_user.id)
                .order_by(desc(HealthRiskScore.period_end), desc(HealthRiskScore.created_at))
                .limit(20)
            )
        ).all()
    )
    if not rows:
        await build_weekly_risk_scores(session, current_user.id)
        rows = list(
            (
                await session.scalars(
                    select(HealthRiskScore)
                    .where(HealthRiskScore.user_id == current_user.id)
                    .order_by(desc(HealthRiskScore.period_end), desc(HealthRiskScore.created_at))
                    .limit(20)
                )
            ).all()
        )

    return {
        "user_id": str(current_user.id),
        "records": [
            {
                "id": str(row.id),
                "date": row.period_end.isoformat(),
                "period_start": row.period_start.isoformat(),
                "period_end": row.period_end.isoformat(),
                "score": row.risk_score,
                "level": row.risk_level,
                "factor": "、".join(row.main_factors) if row.main_factors else "暂无明显风险因素",
                "data_source": "Health Risk Engine",
            }
            for row in rows
        ],
    }
