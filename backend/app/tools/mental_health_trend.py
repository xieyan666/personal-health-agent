"""MentalHealthTrendTool: reads the current user's mental check-in trends.

LLM-free.  Used later by Mental Health Agent to ground support advice in real
check-in data; if no data exists the agent must say so instead of inventing a
stressful state.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import MentalAssessment, MentalCheckin
from backend.app.services.mental_health_service import MOOD_LEVELS, _average
from backend.app.services.data_authorization_service import AuthorizationService


async def get_mental_health_trend_context(session: AsyncSession, user_id: UUID) -> dict:
    """Return 7-day mental state summary for the current user only."""
    since = date.today() - timedelta(days=13)
    rows = list(
        (
            await session.scalars(
                select(MentalCheckin)
                .where(MentalCheckin.user_id == user_id, MentalCheckin.checkin_date >= since)
                .order_by(MentalCheckin.checkin_date)
            )
        ).all()
    )
    recent = [row for row in rows if row.checkin_date >= date.today() - timedelta(days=6)]
    previous = [row for row in rows if row.checkin_date < date.today() - timedelta(days=6)]
    stress_avg_7d = _average([float(row.stress_level) for row in recent])
    stress_avg_prev = _average([float(row.stress_level) for row in previous])
    stress_change = round(stress_avg_7d - stress_avg_prev, 1)
    energy_avg_7d = _average([float(row.energy_level) for row in recent])
    mood_trend = "declining" if stress_avg_7d > stress_avg_prev else "stable"
    counter: Counter[str] = Counter()
    for row in recent:
        for source in row.stress_sources or []:
            counter[source] += 1
    main_stress_sources = [name for name, _ in counter.most_common(2)]
    return {
        "stress_avg_7d": stress_avg_7d,
        "stress_change": stress_change,
        "energy_avg_7d": energy_avg_7d,
        "mood_trend": mood_trend,
        "main_stress_sources": main_stress_sources,
        "checkin_count_7d": len(recent),
    }


async def get_authorized_mental_health_trend_context(session: AsyncSession, user_id: UUID, *, purpose: str) -> dict:
    """Mental Health Agent only: requires its dedicated, never-inherited scope."""
    await AuthorizationService(session).require(user_id=user_id, grantee_type="agent", grantee_id="mental_health_agent", scope="mental_trend.read", purpose=purpose)
    return await get_mental_health_trend_context(session, user_id)


async def get_authorized_mental_assessment_context(
    session: AsyncSession,
    user_id: UUID,
    *,
    purpose: str,
    assessment_id: UUID | None = None,
) -> list[dict]:
    """Expose self-assessment outcomes to the Mental Health Agent only with consent.

    Raw answers remain scoped to this authorised tool boundary; callers receive
    only completed type/version/score/level metadata for non-diagnostic support.
    """
    await AuthorizationService(session).require(
        user_id=user_id,
        grantee_type="agent",
        grantee_id="mental_health_agent",
        scope="mental_assessment.read",
        purpose=purpose,
    )
    query = (
        select(MentalAssessment)
        .where(MentalAssessment.user_id == user_id)
        .order_by(MentalAssessment.completed_at.desc().nullslast())
    )
    if assessment_id is not None:
        # The user scope is deliberately part of this lookup: a browser-held
        # UUID can never be used to read another employee's assessment.
        query = query.where(MentalAssessment.id == assessment_id)
    else:
        query = query.limit(5)
    rows = list(
        (
            await session.scalars(
                query
            )
        ).all()
    )
    if assessment_id is not None and not rows:
        raise LookupError("心理测评结果不存在")
    return [
        {
            "id": str(row.id),
            "assessment_type": row.assessment_type,
            "assessment_version": row.assessment_version,
            "score": row.score,
            "raw_score": row.raw_score,
            "percentage_score": row.percentage_score,
            "level": row.level,
            "display_level": (row.result_summary or {}).get("display_level") or row.level,
            "safety_flag": row.safety_flag,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }
        for row in rows
    ]
