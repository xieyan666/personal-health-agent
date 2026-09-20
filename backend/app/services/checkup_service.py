"""Admin checkup-management aggregation and review operations.

Read-only stats + list/detail over health_check_reports / indicators, plus the
manual-review workflow.  Abnormal-flagging logic stays in the existing rule
engine; this module never re-judges values and never calls an LLM.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.exceptions import NotFoundError, ValidationError
from backend.app.models import Department, Employee, HealthCheckIndicator, HealthCheckReport, User

PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90}
REVIEW_STATUS_MAP = {"parsed": "解析完成", "analyzed": "解析完成", "review_required": "待人工确认", "failed": "解析失败", "parsing": "解析中", "uploaded": "待解析", "partial": "部分解析"}
ABNORMAL_FLAGS = {"high", "low"}


def derived_display_status(report: HealthCheckReport, has_unreviewed_abnormal: bool) -> tuple[str, bool]:
    """Return (display_status, pending_review).  A parsed/analyzed report with
    unreviewed abnormal indicators is shown as 待人工确认."""
    if report.parse_status in {"parsed", "analyzed", "review_required"}:
        if has_unreviewed_abnormal:
            return "待人工确认", True
        return "解析完成", False
    if report.parse_status == "failed":
        return "解析失败", False
    return REVIEW_STATUS_MAP.get(report.parse_status, report.parse_status), False


class CheckupManagementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def departments(self) -> list[str]:
        rows = await self.session.execute(select(Department.name).order_by(Department.name))
        return [name for name in rows.scalars().all() if name]

    async def _reports_in_period(self, period_days: int) -> list[HealthCheckReport]:
        cutoff = datetime.now() - timedelta(days=period_days - 1)
        return list(
            (
                await self.session.scalars(
                    select(HealthCheckReport).where(HealthCheckReport.created_at >= cutoff)
                )
            ).all()
        )

    async def summary(self, period: str = "30d") -> dict:
        days = PERIOD_DAYS.get(period, 30)
        reports = await self._reports_in_period(days)
        report_ids = [report.id for report in reports]
        abnormal_rows = set(
            (
                await self.session.scalars(
                    select(HealthCheckIndicator.report_id)
                    .where(
                        HealthCheckIndicator.report_id.in_(report_ids),
                        HealthCheckIndicator.flag.in_(ABNORMAL_FLAGS),
                    )
                )
            ).all()
        )
        unreviewed_rows = set(
            (
                await self.session.scalars(
                    select(HealthCheckIndicator.report_id)
                    .where(
                        HealthCheckIndicator.report_id.in_(report_ids),
                        HealthCheckIndicator.flag.in_(ABNORMAL_FLAGS),
                        HealthCheckIndicator.review_status.is_(None),
                    )
                )
            ).all()
        )
        parsed_count = sum(1 for report in reports if report.parse_status in {"parsed", "analyzed", "review_required"})
        pending_review = 0
        abnormal_reports = len(abnormal_rows)
        for report in reports:
            _, pending = derived_display_status(report, report.id in unreviewed_rows)
            if pending:
                pending_review += 1

        status_counter: dict[str, int] = {}
        method_counter: dict[str, int] = {}
        for report in reports:
            status, _ = derived_display_status(report, report.id in unreviewed_rows)
            status_counter[status] = status_counter.get(status, 0) + 1
            method = report.parse_mode or report.parse_method or "unknown"
            method_counter[method] = method_counter.get(method, 0) + 1

        total = len(reports) or 1
        return {
            "stats": {
                "total_reports": len(reports),
                "parsed_count": parsed_count,
                "pending_review_reports": pending_review,
                "abnormal_reports": abnormal_reports,
            },
            "status_distribution": [
                {"label": label, "count": count, "percent": round(count / total * 100, 1)}
                for label, count in sorted(status_counter.items(), key=lambda item: item[1], reverse=True)
            ],
            "method_distribution": [
                {"label": label, "count": count, "percent": round(count / total * 100, 1)}
                for label, count in sorted(method_counter.items(), key=lambda item: item[1], reverse=True)
            ],
            "departments": await self.departments(),
        }

    async def list_reports(
        self, *, period: str, department: str | None, status: str | None, method: str | None,
    ) -> list[dict]:
        days = PERIOD_DAYS.get(period, 30)
        reports = await self._reports_in_period(days)
        if department:
            employee_rows = await self.session.execute(
                select(Employee.user_id).where(Employee.department == department)
            )
            dept_user_ids = {user_id for user_id in employee_rows.scalars().all()}
            reports = [report for report in reports if report.user_id in dept_user_ids]
        if method:
            reports = [report for report in reports if (report.parse_mode or report.parse_method) == method]

        report_ids = [report.id for report in reports]
        counts: dict = {}
        if report_ids:
            total_rows = (
                await self.session.execute(
                    select(
                        HealthCheckIndicator.report_id,
                        func.count(HealthCheckIndicator.id),
                    ).where(HealthCheckIndicator.report_id.in_(report_ids)).group_by(HealthCheckIndicator.report_id)
                )
            ).all()
            abnormal_rows = (
                await self.session.execute(
                    select(
                        HealthCheckIndicator.report_id,
                        func.count(HealthCheckIndicator.id),
                    ).where(
                        HealthCheckIndicator.report_id.in_(report_ids),
                        HealthCheckIndicator.flag.in_(ABNORMAL_FLAGS),
                    ).group_by(HealthCheckIndicator.report_id)
                )
            ).all()
            for report_id, total in total_rows:
                counts[report_id] = {"indicator_count": int(total), "abnormal_count": 0}
            for report_id, abnormal in abnormal_rows:
                if report_id in counts:
                    counts[report_id]["abnormal_count"] = int(abnormal)
        unreviewed = set(
            (
                await self.session.scalars(
                    select(HealthCheckIndicator.report_id)
                    .where(
                        HealthCheckIndicator.report_id.in_(report_ids),
                        HealthCheckIndicator.flag.in_(ABNORMAL_FLAGS),
                        HealthCheckIndicator.review_status.is_(None),
                    )
                )
            ).all()
        )
        user_ids = list({report.user_id for report in reports})
        employees = {}
        if user_ids:
            rows = await self.session.execute(
                select(Employee.user_id, Employee.name, Employee.employee_no, User.department)
                .join(User, User.id == Employee.user_id)
                .where(Employee.user_id.in_(user_ids))
            )
            for user_id, name, employee_no, department_name in rows.all():
                employees[user_id] = {"name": name, "employee_no": employee_no, "department": department_name}

        items = []
        for report in reports:
            display, pending = derived_display_status(report, report.id in unreviewed)
            info = employees.get(report.user_id, {})
            count = counts.get(report.id, {"indicator_count": 0, "abnormal_count": 0})
            items.append({
                "id": report.id,
                "employee_name": info.get("name"),
                "employee_no": info.get("employee_no"),
                "department": info.get("department"),
                "report_name": report.report_name,
                "hospital": report.hospital,
                "report_date": report.report_date,
                "uploaded_at": report.created_at,
                "parse_method": report.parse_method,
                "parse_mode": report.parse_mode,
                "indicator_count": count["indicator_count"],
                "abnormal_count": count["abnormal_count"],
                "parse_status": report.parse_status,
                "display_status": display,
                "pending_review": pending,
                "ocr_used": report.ocr_used,
                "parse_error": report.parse_error,
            })
        items.sort(key=lambda item: item["uploaded_at"], reverse=True)
        return items

    async def get_detail(self, report_id: UUID) -> dict:
        report = await self.session.get(HealthCheckReport, report_id)
        if report is None:
            raise NotFoundError("体检报告不存在")
        indicators = list(
            (
                await self.session.scalars(
                    select(HealthCheckIndicator)
                    .where(HealthCheckIndicator.report_id == report_id)
                    .order_by(HealthCheckIndicator.category, HealthCheckIndicator.item_name)
                )
            ).all()
        )
        unreviewed = any(
            indicator.flag in ABNORMAL_FLAGS and indicator.review_status is None
            for indicator in indicators
        )
        display, pending = derived_display_status(report, unreviewed)
        abnormal_count = sum(1 for indicator in indicators if indicator.flag in ABNORMAL_FLAGS)
        user = await self.session.get(User, report.user_id)
        employee = None
        if user:
            employee = await self.session.scalar(
                select(Employee).where(Employee.user_id == user.id)
            )
        return {
            "id": report.id,
            "employee_name": employee.name if employee else (user.display_name if user else None),
            "employee_no": employee.employee_no if employee else None,
            "department": employee.department if employee else None,
            "report_name": report.report_name,
            "hospital": report.hospital,
            "report_date": report.report_date,
            "uploaded_at": report.created_at,
            "parse_method": report.parse_method,
            "parse_mode": report.parse_mode,
            "indicator_count": len(indicators),
            "abnormal_count": abnormal_count,
            "parse_status": report.parse_status,
            "display_status": display,
            "pending_review": pending,
            "ocr_used": report.ocr_used,
            "parse_error": report.parse_error,
            "parse_warnings": report.parse_warnings,
            "parsed_at": report.parsed_at,
            "items": [
                {
                    "id": indicator.id,
                    "item_name": indicator.item_name,
                    "value": float(indicator.value),
                    "value_text": indicator.value_text,
                    "unit": indicator.unit,
                    "reference_text": indicator.reference_text,
                    "flag": indicator.flag,
                    "source_type": indicator.source_type,
                    "confidence": float(indicator.confidence) if indicator.confidence is not None else None,
                    "review_status": indicator.review_status,
                    "reviewed_value": float(indicator.reviewed_value) if indicator.reviewed_value is not None else None,
                    "review_note": indicator.review_note,
                }
                for indicator in indicators
            ],
        }

    async def review_indicator(self, indicator_id: UUID, actor_id: UUID, *, action: str, reviewed_value: float | None, note: str | None):
        indicator = await self.session.get(HealthCheckIndicator, indicator_id)
        if indicator is None:
            raise NotFoundError("指标不存在")
        now = datetime.now()
        if action == "confirm":
            indicator.review_status = "confirmed"
        elif action == "modify":
            if reviewed_value is None:
                raise ValidationError("修改指标必须提供修正值")
            indicator.review_status = "modified"
            indicator.reviewed_value = reviewed_value
        elif action == "ignore":
            indicator.review_status = "ignored"
        else:
            raise ValidationError(f"不支持的操作: {action}")
        indicator.reviewed_by_id = actor_id
        indicator.reviewed_at = now
        if note:
            indicator.review_note = note
        await self.session.commit()
        return indicator
