"""Mental wellness operations: check-ins, trends, workload statistics.

All queries are scoped by the JWT user id.  Statistics are computed from the
persisted check-in rows only — never from an LLM.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import MentalAssessment, MentalCheckin
from backend.app.schemas.mental_health import MentalAssessmentCreate, MentalCheckinCreate, MentalTrendPoint
from backend.app.services.mental_assessment_scoring import MentalAssessmentScoringService

MOOD_LEVELS = {"很好": 5, "不错": 4, "一般": 3, "有压力": 2, "状态较差": 1}
HIGH_STRESS_THRESHOLD = 7


def _mood_value(mood: str) -> float:
    return float(MOOD_LEVELS.get(mood, 3))


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


async def get_today_checkin(session: AsyncSession, user_id: UUID, when: date | None = None) -> MentalCheckin | None:
    target = when or date.today()
    return await session.scalar(
        select(MentalCheckin).where(MentalCheckin.user_id == user_id, MentalCheckin.checkin_date == target)
    )


async def upsert_checkin(session: AsyncSession, user_id: UUID, payload: MentalCheckinCreate, when: date | None = None) -> MentalCheckin:
    """Save (or update) today's check-in. One record per day per user."""
    target = when or date.today()
    existing = await get_today_checkin(session, user_id, target)
    if existing is None:
        existing = MentalCheckin(user_id=user_id, checkin_date=target)
        session.add(existing)
    existing.mood = payload.mood
    existing.stress_level = payload.stress_level
    existing.energy_level = payload.energy_level
    existing.sleep_feeling = payload.sleep_feeling
    existing.stress_sources = list(payload.stress_sources)
    existing.note = payload.note
    await session.commit()
    await session.refresh(existing)
    return existing


async def get_checkins_since(session: AsyncSession, user_id: UUID, days: int, limit: int = 200) -> list[MentalCheckin]:
    since = date.today() - timedelta(days=days - 1)
    return list(
        (
            await session.scalars(
                select(MentalCheckin)
                .where(MentalCheckin.user_id == user_id, MentalCheckin.checkin_date >= since)
                .order_by(MentalCheckin.checkin_date)
                .limit(limit)
            )
        ).all()
    )


def _trend_values(checkins: list[MentalCheckin], trend_type: str) -> list[tuple[date, float]]:
    values: list[tuple[date, float]] = []
    for checkin in checkins:
        if trend_type == "mood":
            value = _mood_value(checkin.mood)
        elif trend_type == "stress":
            value = float(checkin.stress_level)
        elif trend_type == "energy":
            value = float(checkin.energy_level)
        else:
            continue
        values.append((checkin.checkin_date, value))
    return values


def _period_stats(values: list[tuple[date, float]], start: date, end: date) -> tuple[list[MentalTrendPoint], float]:
    """Fill the window day-by-day; missing days are omitted from the line."""
    points: list[MentalTrendPoint] = []
    bucket = {day: value for day, value in values if start <= day <= end}
    day = start
    while day <= end:
        if day in bucket:
            points.append(MentalTrendPoint(date=day.isoformat(), value=bucket[day]))
        day += timedelta(days=1)
    return points, _average([value for day, value in values if start <= day <= end])


async def get_trends(session: AsyncSession, user_id: UUID, trend_type: str, days: int) -> dict:
    """Trend for the latest ``days`` window vs the previous window of same length."""
    current_start = date.today() - timedelta(days=days - 1)
    previous_start = current_start - timedelta(days=days)
    all_values = await get_checkins_since(session, user_id, days * 2)
    values = _trend_values(all_values, trend_type)
    points, average = _period_stats(values, current_start, date.today())
    _, previous_average = _period_stats(values, previous_start, current_start - timedelta(days=1))
    change = round(average - previous_average, 1)
    return {
        "type": trend_type,
        "period": days,
        "average": average,
        "change": change,
        "data": [point.model_dump() for point in points],
    }


def _recovery_status(avg_energy: float) -> str:
    if avg_energy <= 0:
        return "暂无数据"
    if avg_energy >= 7:
        return "良好"
    if avg_energy >= 5:
        return "一般"
    return "较差"


async def get_workload(session: AsyncSession, user_id: UUID) -> dict:
    """Weekly work-pressure analysis computed from the last 7 check-ins' days."""
    since = date.today() - timedelta(days=6)
    checkins = await get_checkins_since(session, user_id, 7)
    week_rows = [row for row in checkins if row.checkin_date >= since]
    if not week_rows:
        return {
            "week_avg_stress": 0.0,
            "high_stress_days": 0,
            "avg_energy": 0.0,
            "recovery_status": "暂无数据",
            "stress_sources": [],
            "has_data": False,
        }
    week_avg_stress = _average([float(row.stress_level) for row in week_rows])
    high_stress_days = sum(1 for row in week_rows if row.stress_level >= HIGH_STRESS_THRESHOLD)
    avg_energy = _average([float(row.energy_level) for row in week_rows])
    counter: Counter[str] = Counter()
    for row in week_rows:
        for source in row.stress_sources or []:
            counter[source] += 1
    total = sum(counter.values())
    shares = [
        {"name": name, "percent": round(count / total * 100, 1)}
        for name, count in counter.most_common()
    ] if total else []
    return {
        "week_avg_stress": week_avg_stress,
        "high_stress_days": high_stress_days,
        "avg_energy": avg_energy,
        "recovery_status": _recovery_status(avg_energy),
        "stress_sources": shares,
        "has_data": True,
    }


async def list_recent_assessments(session: AsyncSession, user_id: UUID, limit: int = 50) -> list[MentalAssessment]:
    return list(
        (
            await session.scalars(
                select(MentalAssessment)
                .where(MentalAssessment.user_id == user_id)
                .order_by(MentalAssessment.completed_at.desc().nullslast(), MentalAssessment.created_at.desc())
                .limit(limit)
            )
        ).all()
    )


async def create_assessment(
    session: AsyncSession,
    user_id: UUID,
    payload: MentalAssessmentCreate,
) -> MentalAssessment:
    """Score and persist a self-assessment for the authenticated employee.

    The scorer reads only the versioned definition.  It never delegates scoring
    to an LLM and it refuses an unconfigured questionnaire.
    """
    result = MentalAssessmentScoringService().score(
        payload.assessment_type,
        payload.assessment_version,
        [answer.model_dump() for answer in payload.answers],
    )
    row = MentalAssessment(
        user_id=user_id,
        assessment_type=payload.assessment_type,
        assessment_version=payload.assessment_version,
        score=result.score,
        raw_score=result.raw_score,
        percentage_score=result.percentage_score,
        level=result.level,
        needs_follow_up=result.needs_follow_up,
        safety_flag=result.safety_flag,
        safety_reason=result.safety_reason,
        answers={answer.question_id: answer.value for answer in payload.answers},
        result_summary=result.summary,
        completed_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row
