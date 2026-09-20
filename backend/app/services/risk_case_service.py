"""Admin risk-case operations: discovery (lazy sync from risk assessments),
listing, detail with action history, status transitions and plan/service links.

The Risk Engine remains the only source of "is there a risk / what level".
This service only wraps those results into a disposition workflow.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.exceptions import NotFoundError, ForbiddenError, ValidationError
from backend.app.models import (
    Department,
    HealthPlan,
    HealthService,
    RiskAssessment,
    RiskCase,
    RiskCaseAction,
    User,
)

RISK_LABELS = {
    "sleep": "睡眠不足",
    "exercise": "运动不足",
    "abnormal": "体检指标异常",
    "stress": "心理压力偏高",
    "heart_rate": "心率异常趋势",
}
RISK_SUMMARIES = {
    "sleep": "近7天睡眠时长持续偏低",
    "exercise": "近30天运动量低于推荐水平",
    "abnormal": "最新体检存在需要关注的异常指标",
    "stress": "近期压力水平偏高",
    "heart_rate": "静息心率呈上升趋势",
}
SOURCE_LABELS = {
    "Wearable": "健康趋势",
    "HealthCheck": "体检报告",
    "MentalCheckin": "心理打卡",
    "RiskTrend": "风险趋势",
}
ACTIVE_STATUSES = {"pending", "confirmed", "processing", "observing"}


class RiskCaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # discovery
    # ------------------------------------------------------------------
    async def sync_cases_from_assessments(self) -> int:
        """Materialise medium/high risk assessments of the last 90 days into
        pending risk cases (idempotent, one case per assessment)."""
        cutoff = datetime.now() - timedelta(days=90)
        existing_assessment_ids = set(
            (
                await self.session.scalars(select(RiskCase.risk_assessment_id))
            ).all()
        )
        rows = (
            await self.session.execute(
                select(RiskAssessment, User.department)
                .join(User, User.id == RiskAssessment.user_id)
                .where(
                    RiskAssessment.level.in_(["medium", "high"]),
                    RiskAssessment.assessed_at >= cutoff,
                    RiskAssessment.id.not_in(existing_assessment_ids) if existing_assessment_ids else True,
                )
                .order_by(RiskAssessment.assessed_at.desc())
                .limit(500)
            )
        ).all()
        created = 0
        for assessment, department in rows:
            if assessment.id in existing_assessment_ids:
                continue
            self.session.add(
                RiskCase(
                    risk_assessment_id=assessment.id,
                    user_id=assessment.user_id,
                    risk_type=assessment.risk_type,
                    risk_level=assessment.level,
                    source=assessment.source,
                    department=department,
                    status="pending",
                )
            )
            created += 1
        if created:
            await self.session.commit()
        return created

    # ------------------------------------------------------------------
    # list / detail
    # ------------------------------------------------------------------
    async def list_cases(
        self,
        *,
        department: str | None = None,
        level: str | None = None,
        source: str | None = None,
        status: str | None = None,
        period_days: int = 30,
    ) -> list[RiskCase]:
        cutoff = datetime.now() - timedelta(days=period_days)
        statement = select(RiskCase).where(RiskCase.created_at >= cutoff)
        if department:
            statement = statement.where(RiskCase.department == department)
        if level:
            statement = statement.where(RiskCase.risk_level == level)
        if source:
            statement = statement.where(RiskCase.source == source)
        if status:
            statement = statement.where(RiskCase.status == status)
        statement = statement.order_by(RiskCase.updated_at.desc())
        return list((await self.session.scalars(statement)).all())

    async def get_case(self, case_id: UUID) -> RiskCase:
        case = await self.session.get(RiskCase, case_id)
        if case is None:
            raise NotFoundError("风险事件不存在")
        return case

    async def get_case_actions(self, case_id: UUID) -> list[RiskCaseAction]:
        rows = (
            await self.session.execute(
                select(RiskCaseAction, User.display_name)
                .outerjoin(User, User.id == RiskCaseAction.actor_user_id)
                .where(RiskCaseAction.risk_case_id == case_id)
                .order_by(RiskCaseAction.created_at)
            )
        ).all()
        actions = list(rows)
        for action, _ in actions:
            pass
        return [action for action, _ in actions]

    async def list_actor_names(self, actor_ids: list[UUID]) -> dict:
        if not actor_ids:
            return {}
        rows = await self.session.execute(
            select(User.id, User.display_name).where(User.id.in_(actor_ids))
        )
        return {user_id: name for user_id, name in rows.all()}

    async def stats(self, period_days: int = 30) -> dict:
        cutoff = datetime.now() - timedelta(days=period_days)
        month_start = date.today().replace(day=1)
        cases = list(
            (
                await self.session.scalars(
                    select(RiskCase).where(RiskCase.created_at >= cutoff)
                )
            ).all()
        )
        pending = sum(1 for case in cases if case.status == "pending")
        high_priority = sum(
            1 for case in cases
            if case.risk_level == "high" and case.status in ACTIVE_STATUSES
        )
        processing = sum(
            1 for case in cases if case.status in {"confirmed", "processing", "observing"}
        )
        closed = sum(
            1 for case in cases
            if case.status in {"resolved", "ignored"}
            and (case.resolved_at or case.ignored_at) is not None
            and (case.resolved_at or case.ignored_at).date() >= month_start
        )
        return {
            "pending": pending,
            "high_priority": high_priority,
            "processing": processing,
            "closed_this_month": closed,
        }

    async def departments(self) -> list[str]:
        rows = await self.session.execute(
            select(Department.name).order_by(Department.name)
        )
        return [name for name in rows.scalars().all() if name]

    # ------------------------------------------------------------------
    # operations
    # ------------------------------------------------------------------
    async def _record_action(self, case_id: UUID, actor_id: UUID, action: str, note: str | None) -> None:
        self.session.add(
            RiskCaseAction(risk_case_id=case_id, actor_user_id=actor_id, action=action, note=note)
        )

    async def transition(self, case_id: UUID, actor_id: UUID, *, action: str, note: str | None, ignore_reason: str | None, next_review_days: int | None) -> RiskCase:
        case = await self.get_case(case_id)
        now = datetime.now()
        if action == "confirm":
            if case.status != "pending":
                raise ValidationError("仅待处理的风险可确认")
            case.status = "confirmed"
            case.confirmed_at = now
            await self._record_action(case_id, actor_id, "confirm", note or "确认风险")
        elif action == "observe":
            if case.status not in {"confirmed", "processing"}:
                raise ValidationError("仅已确认或处理中的风险可设置持续观察")
            case.status = "observing"
            case.next_review_at = now + timedelta(days=next_review_days or 14)
            await self._record_action(
                case_id, actor_id, "observe",
                note or f"设置持续观察，{next_review_days or 14}天后复查",
            )
        elif action == "resolve":
            if case.status in {"resolved", "ignored"}:
                raise ValidationError("该风险已关闭")
            case.status = "resolved"
            case.resolved_at = now
            case.resolved_by_id = actor_id
            case.resolution_note = note
            await self._record_action(case_id, actor_id, "resolve", note or "标记已解决")
        elif action == "ignore":
            if case.status in {"resolved", "ignored"}:
                raise ValidationError("该风险已关闭")
            if not ignore_reason:
                raise ValidationError("忽略风险必须填写原因")
            case.status = "ignored"
            case.ignored_at = now
            case.ignored_by_id = actor_id
            case.ignore_reason = ignore_reason
            await self._record_action(case_id, actor_id, "ignore", ignore_reason)
        else:
            raise ValidationError(f"不支持的操作: {action}")
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def link_plan(self, case_id: UUID, actor_id: UUID, plan_id: UUID) -> RiskCase:
        case = await self.get_case(case_id)
        plan = await self.session.get(HealthPlan, plan_id)
        if plan is None:
            raise NotFoundError("健康计划不存在")
        if plan.user_id != case.user_id:
            raise ForbiddenError("只能关联该员工自己的健康计划")
        case.assigned_plan_id = plan.id
        if case.status in {"pending", "confirmed"}:
            case.status = "processing"
        await self._record_action(case_id, actor_id, "link_plan", f"关联「{plan.plan_name}」")
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def link_service(self, case_id: UUID, actor_id: UUID, service_id: UUID) -> RiskCase:
        case = await self.get_case(case_id)
        service = await self.session.get(HealthService, service_id)
        if service is None or service.status != "active":
            raise NotFoundError("健康服务不存在或已下线")
        case.assigned_service_id = service.id
        if case.status in {"pending", "confirmed"}:
            case.status = "processing"
        await self._record_action(case_id, actor_id, "link_service", f"关联「{service.name}」")
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def add_action(self, case_id: UUID, actor_id: UUID, action: str, note: str | None) -> RiskCaseAction:
        case = await self.get_case(case_id)
        await self._record_action(case_id, actor_id, action, note)
        await self.session.commit()
        return case

    async def options(self, user_id: UUID) -> dict:
        services = list(
            (
                await self.session.scalars(
                    select(HealthService)
                    .where(HealthService.status == "active")
                    .order_by(HealthService.sort_order, HealthService.name)
                )
            ).all()
        )
        plans = list(
            (
                await self.session.scalars(
                    select(HealthPlan)
                    .where(HealthPlan.user_id == user_id)
                    .order_by(HealthPlan.start_date.desc())
                )
            ).all()
        )
        return {
            "services": [
                {
                    "id": service.id,
                    "name": service.name,
                    "category": service.category,
                    "description": service.description,
                    "delivery_mode": service.delivery_mode,
                }
                for service in services
            ],
            "plans": [
                {
                    "id": plan.id,
                    "plan_name": plan.plan_name,
                    "plan_type": plan.plan_type,
                    "status": plan.status,
                }
                for plan in plans
            ],
        }

    def risk_summary(self, case: RiskCase) -> str:
        summary = RISK_SUMMARIES.get(case.risk_type)
        if summary is None:
            summary = f"存在{RISK_LABELS.get(case.risk_type, case.risk_type)}风险"
        return summary


def case_to_dict(case: RiskCase) -> dict:
    return {
        "id": case.id,
        "risk_assessment_id": case.risk_assessment_id,
        "user_id": case.user_id,
        "risk_type": case.risk_type,
        "risk_level": case.risk_level,
        "source": case.source,
        "department": case.department,
        "status": case.status,
        "assigned_plan_id": case.assigned_plan_id,
        "assigned_service_id": case.assigned_service_id,
        "next_review_at": case.next_review_at,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "confirmed_at": case.confirmed_at,
        "resolved_at": case.resolved_at,
        "resolution_note": case.resolution_note,
        "ignore_reason": case.ignore_reason,
        "resolved_by_id": case.resolved_by_id,
        "ignored_by_id": case.ignored_by_id,
    }
