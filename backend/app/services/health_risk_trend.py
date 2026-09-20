"""Weekly health-risk scoring based exclusively on persisted health data and rules."""

from datetime import date, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import ExerciseRecord, HealthProfile, HealthRiskScore, HeartRateRecord, SleepRecord, HealthCheckIndicator, HealthCheckReport


def _level(score: int) -> str:
    if score >= 90:
        return "良好"
    if score >= 75:
        return "稳定"
    if score >= 60:
        return "需关注"
    return "风险较高"


async def _average(session: AsyncSession, column, model, user_id, start: date, end: date) -> float | None:
    value = await session.scalar(select(func.avg(column)).where(model.user_id == user_id, model.record_date >= start, model.record_date <= end))
    return float(value) if value is not None else None


async def build_weekly_risk_scores(session: AsyncSession, user_id, end: date | None = None) -> list[HealthRiskScore]:
    """Build five contiguous assessment periods for the latest 30 days."""
    end = end or date.today()
    start = end - timedelta(days=29)
    profile = await session.scalar(select(HealthProfile).where(HealthProfile.user_id == user_id))
    bmi = None
    if profile and profile.height and profile.weight:
        bmi = float(profile.weight) / ((float(profile.height) / 100) ** 2)
    latest_report = await session.scalar(select(HealthCheckReport).where(HealthCheckReport.user_id == user_id).order_by(HealthCheckReport.report_date.desc()).limit(1))
    report_abnormal_count = 0
    if latest_report is not None:
        report_abnormal_count = int(await session.scalar(select(func.count(HealthCheckIndicator.id)).where(HealthCheckIndicator.report_id == latest_report.id, HealthCheckIndicator.flag.in_(("high", "low")))) or 0)

    await session.execute(delete(HealthRiskScore).where(HealthRiskScore.user_id == user_id, HealthRiskScore.period_start >= start, HealthRiskScore.period_end <= end))
    records: list[HealthRiskScore] = []
    for index in range(5):
        period_start = start + timedelta(days=index * 7)
        period_end = min(period_start + timedelta(days=6), end)
        sleep = await _average(session, SleepRecord.sleep_duration, SleepRecord, user_id, period_start, period_end)
        exercise = await _average(session, ExerciseRecord.exercise_duration, ExerciseRecord, user_id, period_start, period_end)
        heart_rate = await _average(session, HeartRateRecord.resting_heart_rate, HeartRateRecord, user_id, period_start, period_end)
        score = 100
        factors: list[str] = []
        if sleep is not None and sleep < 6:
            score -= 20; factors.append("睡眠不足")
        elif sleep is not None and sleep < 7:
            score -= 8; factors.append("睡眠低于推荐范围")
        if exercise is not None and exercise * 7 < 150:
            score -= 8; factors.append("运动达标率下降")
        if heart_rate is not None and heart_rate > 90:
            score -= 8; factors.append("静息心率偏高")
        if bmi is not None and not 18.5 <= bmi < 24:
            score -= 6; factors.append("BMI未处于推荐范围")
        if report_abnormal_count:
            score -= min(12, report_abnormal_count * 6); factors.append("体检报告异常指标")
        record = HealthRiskScore(user_id=user_id, period_start=period_start, period_end=period_end, risk_score=max(0, score), risk_level=_level(max(0, score)), main_factors=factors)
        session.add(record); records.append(record)
    await session.commit()
    return records
