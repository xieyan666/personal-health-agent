"""Aggregated, anonymous health analytics for the admin dashboard.

Read-only SELECT / GROUP BY / COUNT aggregation over the existing health
tables.  Never runs the Risk / Report agents or an LLM, and never returns
per-employee sensitive values (no names, no personal indicator values).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import (
    Department,
    HealthCheckIndicator,
    HealthCheckReport,
    HealthPlan,
    HealthProfile,
    HealthRiskScore,
    RiskAssessment,
    User,
)
from backend.app.schemas.admin_analytics import (
    AnalyticsOverview,
    DepartmentStat,
    HealthAnalyticsSummary,
    HealthDistributionItem,
    RiskRankingItem,
    TrendPoint,
)

ATTENTION_LEVELS = {"需要关注", "重点关注"}
HEALTHY_LEVELS = {"良好", "稳定"}
ABNORMAL_FLAGS = {"high", "low"}
ACTIVE_PLAN_STATUS = {"active", "completed"}
PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90}

RISK_LABELS = {
    "sleep": "睡眠不足",
    "exercise": "运动不足",
    "heart_rate": "心率异常趋势",
    "stress": "心理压力偏高",
    "abnormal": "体检指标异常",
    "workload": "工作负荷偏重",
    "diet": "饮食结构不合理",
}


def _label(risk_type: str) -> str:
    return RISK_LABELS.get(risk_type, risk_type)


class HealthAnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    async def _employees(self, department: str | None) -> list[User]:
        statement = select(User).where(User.role == "employee", User.status == "active")
        if department:
            if department == "未分组":
                statement = statement.where(User.department.is_(None))
            else:
                statement = statement.where(User.department == department)
        return list((await self.session.scalars(statement)).all())

    async def _user_ids_in(self, model, column, user_ids: list) -> set:
        if not user_ids:
            return set()
        statement = select(distinct(column)).where(column.in_(user_ids))
        return set((await self.session.scalars(statement)).all())

    async def _latest_risk_levels(self, user_ids: list) -> dict:
        """Latest health_risk_score per user -> risk_level (Chinese)."""
        if not user_ids:
            return {}
        rows = list(
            (
                await self.session.execute(
                    select(
                        HealthRiskScore.user_id,
                        HealthRiskScore.risk_level,
                        func.row_number().over(
                            partition_by=HealthRiskScore.user_id,
                            order_by=HealthRiskScore.period_end.desc(),
                        ).label("rn"),
                    ).where(HealthRiskScore.user_id.in_(user_ids))
                )
            ).all()
        )
        return {row.user_id: row.risk_level for row in rows if row.rn == 1}

    async def _high_risk_assessment_users(self, user_ids: list, cutoff: date) -> set:
        if not user_ids:
            return set()
        statement = select(distinct(RiskAssessment.user_id)).where(
            RiskAssessment.user_id.in_(user_ids),
            RiskAssessment.level == "high",
            RiskAssessment.assessed_at >= cutoff,
        )
        return set((await self.session.scalars(statement)).all())

    # ------------------------------------------------------------------
    # main
    # ------------------------------------------------------------------
    async def summary(self, period: str = "30d", department: str | None = None) -> HealthAnalyticsSummary:
        days = PERIOD_DAYS.get(period, 30)
        cutoff = date.today() - timedelta(days=days - 1)
        employees = await self._employees(department)
        user_ids = [user.id for user in employees]
        if not user_ids:
            return HealthAnalyticsSummary(period=period, department=department)

        covered = set(await self._user_ids_in(HealthProfile, HealthProfile.user_id, user_ids))
        covered |= set(await self._user_ids_in(HealthRiskScore, HealthRiskScore.user_id, user_ids))
        covered |= set(await self._user_ids_in(HealthCheckReport, HealthCheckReport.user_id, user_ids))

        latest_levels = await self._latest_risk_levels(user_ids)
        attention = {
            user_id for user_id, level in latest_levels.items() if level in ATTENTION_LEVELS
        }
        attention |= await self._high_risk_assessment_users(user_ids, cutoff)

        report_users = set(
            (
                await self.session.scalars(
                    select(HealthCheckReport.user_id).where(HealthCheckReport.user_id.in_(user_ids))
                )
            ).all()
        )
        abnormal_exam: set = set()
        if report_users:
            abnormal_exam = set(
                (
                    await self.session.scalars(
                        select(distinct(HealthCheckReport.user_id)).where(
                            HealthCheckReport.user_id.in_(report_users),
                            HealthCheckReport.id.in_(
                                select(HealthCheckIndicator.report_id).where(
                                    HealthCheckIndicator.flag.in_(ABNORMAL_FLAGS)
                                )
                            ),
                        )
                    )
                ).all()
            )

        plan_users = set(
            (
                await self.session.scalars(
                    select(HealthPlan.user_id).where(
                        HealthPlan.user_id.in_(user_ids),
                        HealthPlan.status.in_(ACTIVE_PLAN_STATUS),
                    )
                )
            ).all()
        )

        total = len(employees)
        overview = AnalyticsOverview(
            total_employees=total,
            covered_employees=len(covered),
            coverage_rate=round(len(covered) / total * 100, 1),
            attention_employees=len(attention),
            attention_rate=round(len(attention) / total * 100, 1),
            abnormal_exam_employees=len(abnormal_exam),
            plan_participants=len(plan_users),
            plan_participation_rate=round(len(plan_users) / total * 100, 1),
        )

        distribution = self._distribution(latest_levels, total)

        risk_ranking = await self._risk_ranking(user_ids, cutoff)

        department_stats = await self._department_stats(department)

        risk_trend = await self._risk_trend(user_ids, cutoff, days)
        available_departments = await self._all_departments()

        return HealthAnalyticsSummary(
            period=period,
            department=department,
            overview=overview,
            health_distribution=distribution,
            risk_ranking=risk_ranking,
            department_stats=department_stats,
            risk_trend=risk_trend,
            available_departments=available_departments,
        )

    def _distribution(self, latest_levels: dict, total: int) -> list[HealthDistributionItem]:
        counter: Counter[str] = Counter(latest_levels.values())
        items = [
            HealthDistributionItem(level="good", label="良好", count=counter.get("良好", 0), percent=0.0),
            HealthDistributionItem(level="stable", label="稳定", count=counter.get("稳定", 0), percent=0.0),
            HealthDistributionItem(level="attention", label="需要关注", count=counter.get("需要关注", 0), percent=0.0),
            HealthDistributionItem(level="critical", label="重点关注", count=counter.get("重点关注", 0), percent=0.0),
        ]
        unevaluated = total - sum(item.count for item in items)
        if unevaluated > 0:
            items.append(HealthDistributionItem(level="unknown", label="暂无数据", count=unevaluated, percent=0.0))
        for item in items:
            item.percent = round(item.count / total * 100, 1)
        return items

    async def _risk_ranking(self, user_ids: list, cutoff: date) -> list[RiskRankingItem]:
        rows = (
            await self.session.execute(
                select(RiskAssessment.risk_type, func.count(distinct(RiskAssessment.user_id))).where(
                    RiskAssessment.user_id.in_(user_ids),
                    RiskAssessment.assessed_at >= cutoff,
                ).group_by(RiskAssessment.risk_type)
            )
        ).all()
        evaluated_users = set(
            (
                await self.session.scalars(
                    select(distinct(RiskAssessment.user_id)).where(
                        RiskAssessment.user_id.in_(user_ids),
                        RiskAssessment.assessed_at >= cutoff,
                    )
                )
            ).all()
        )
        denominator = len(evaluated_users) or 1
        ranking = [
            RiskRankingItem(risk_type=risk_type, label=_label(risk_type), count=count, percent=round(count / denominator * 100, 1))
            for risk_type, count in rows
        ]
        ranking.sort(key=lambda item: item.count, reverse=True)
        return ranking[:5]

    async def _all_departments(self) -> list[str]:
        """Return every department from the RBAC department table, matching the
        options shown in the admin user-management screen.  Always reflects
        the authoritative department list, so the filter dropdown never
        surfaces a synthetic "未分组" entry."""
        rows = await self.session.execute(
            select(Department.name).order_by(Department.name)
        )
        return [name for name in rows.scalars().all() if name]

    async def _department_stats(self, requested: str | None) -> list[DepartmentStat]:
        employees = await self._employees(None)
        # Restrict the table to departments the admin can actually manage
        # (the RBAC department table).  Historical / unlisted values
        # ("未分组", "AI研发", …) are hidden so the dashboard matches the
        # user-management department list exactly.
        allowed = set(await self._all_departments())
        groups: dict[str, list[User]] = defaultdict(list)
        for user in employees:
            if not user.department or user.department not in allowed:
                continue
            groups[user.department].append(user)
        if not groups:
            return []
        stats: list[DepartmentStat] = []
        for department_name, members in groups.items():
            ids = [user.id for user in members]
            total = len(ids)
            covered = set(await self._user_ids_in(HealthProfile, HealthProfile.user_id, ids))
            covered |= set(await self._user_ids_in(HealthRiskScore, HealthRiskScore.user_id, ids))
            covered |= set(await self._user_ids_in(HealthCheckReport, HealthCheckReport.user_id, ids))
            latest_levels = await self._latest_risk_levels(ids)
            healthy = sum(1 for level in latest_levels.values() if level in HEALTHY_LEVELS)
            attention_set = {
                user_id for user_id, level in latest_levels.items() if level in ATTENTION_LEVELS
            }
            attention_set |= await self._high_risk_assessment_users(ids, date.today() - timedelta(days=29))
            top_risk: str | None = None
            rows = (
                await self.session.execute(
                    select(RiskAssessment.risk_type, func.count(RiskAssessment.id)).where(
                        RiskAssessment.user_id.in_(ids),
                    ).group_by(RiskAssessment.risk_type).order_by(func.count(RiskAssessment.id).desc()).limit(1)
                )
            ).all()
            if rows:
                top_risk = _label(rows[0][0])
            stats.append(
                DepartmentStat(
                    department=department_name,
                    total=total,
                    coverage_rate=round(len(covered) / total * 100, 1) if total else 0.0,
                    healthy_rate=round(healthy / total * 100, 1) if total else 0.0,
                    attention_count=len(attention_set),
                    attention_rate=round(len(attention_set) / total * 100, 1) if total else 0.0,
                    top_risk=top_risk,
                    sample_too_small=total < 5,
                )
            )
        if requested:
            stats = [stat for stat in stats if stat.department == requested]
        return stats

    async def _risk_trend(self, user_ids: list, cutoff: date, days: int) -> list[TrendPoint]:
        rows = (
            await self.session.execute(
                select(
                    HealthRiskScore.period_end,
                    HealthRiskScore.risk_level,
                ).where(
                    HealthRiskScore.user_id.in_(user_ids),
                    HealthRiskScore.period_end >= cutoff,
                ).order_by(HealthRiskScore.period_end)
            )
        ).all()
        buckets: dict[date, list[str]] = defaultdict(list)
        for period_end, level in rows:
            buckets[period_end].append(level)
        trend: list[TrendPoint] = []
        for week_end in sorted(buckets):
            levels = buckets[week_end]
            attention_count = sum(1 for level in levels if level in ATTENTION_LEVELS)
            trend.append(
                TrendPoint(
                    period=week_end.isoformat(),
                    label=f"{week_end.month}/{week_end.day}周",
                    value=round(attention_count / len(levels) * 100, 1),
                    evaluated=len(levels),
                )
            )
        return trend[-8:]
