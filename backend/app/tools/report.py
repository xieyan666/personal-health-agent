"""ReportTool: read parsed, structured health-report indicators for an owner.

The tool is strictly read-only.  It loads ``health_check_reports`` and the
already-parsed ``health_check_indicators`` rows for the current JWT user; a
report belonging to another employee is never exposed.

Parser recognises, rule engine judges, agent explains.  This tool only hands
the agent the auditable structured facts.  Ownership is enforced by binding
``user_id`` (from the JWT) into the tool handler closure -- it is never
accepted from tool arguments, so the frontend cannot read another employee's
report.
"""

from __future__ import annotations

import json as _json
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import HealthCheckIndicator, HealthCheckReport
from backend.app.tools.base import ToolDefinition, ToolResult
from backend.app.services.data_authorization_service import AuthorizationService, DataAccessNotAuthorized


def _indicator_to_dict(item: HealthCheckIndicator) -> dict[str, Any]:
    value = float(item.value) if item.value is not None else None
    return {
        "name": item.item_name,
        "code": item.code,
        "value": value,
        "value_text": (item.value_text or (str(value) if value is not None else None)),
        "unit": item.unit,
        "reference_text": item.reference_text,
        "reference_min": float(item.reference_min) if item.reference_min is not None else None,
        "reference_max": float(item.reference_max) if item.reference_max is not None else None,
        "flag": item.flag,
        "category": item.category,
        "source_type": item.source_type,
        "source_page": item.source_page,
        "confidence": float(item.confidence) if item.confidence is not None else None,
    }


async def get_report_analysis_context(session: AsyncSession, user_id: UUID, report_id: UUID) -> dict[str, Any] | None:
    """Return the structured report payload for the report owner, or None.

    Ownership is enforced here so callers can never read another employee's
    report, even if they pass an arbitrary report_id.
    """
    report = await session.get(HealthCheckReport, report_id)
    if report is None or report.user_id != user_id:
        return None
    rows = list(
        (
            await session.scalars(
                select(HealthCheckIndicator)
                .where(HealthCheckIndicator.report_id == report_id)
                .order_by(HealthCheckIndicator.category, HealthCheckIndicator.item_name)
            )
        ).all()
    )
    items = [_indicator_to_dict(item) for item in rows]
    counts = {"total_items": len(items), "normal_count": 0, "high_count": 0, "low_count": 0, "unknown_count": 0}
    for item in items:
        flag = item["flag"]
        key = f"{flag}_count"
        if key in counts:
            counts[key] += 1
    return {
        "report": {
            "report_id": str(report.id),
            "report_date": report.report_date.isoformat(),
            "hospital": report.hospital,
            "parse_mode": report.parse_mode,
            "ocr_used": report.ocr_used,
        },
        "summary": counts,
        "items": items,
    }


REPORT_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"report_id": {"type": "string", "description": "体检报告 ID（UUID）"}},
    "required": ["report_id"],
    "additionalProperties": False,
}


def build_report_tool(session: AsyncSession, user_id: UUID) -> ToolDefinition:
    """Build a user-bound ReportTool definition.

    ``user_id`` comes from the JWT at request time and is captured in the
    handler closure; the model can only request which report_id to read.
    """

    async def handler(arguments: Mapping[str, Any]) -> ToolResult:
        try:
            await AuthorizationService(session).require(
                user_id=user_id,
                grantee_type="agent",
                grantee_id="report_agent",
                scope="health_report.read",
                purpose="用于 AI Report Agent 解读用户指定的体检报告",
            )
        except DataAccessNotAuthorized:
            return ToolResult(False, "DATA_ACCESS_NOT_AUTHORIZED:health_report.read")
        raw_report_id = arguments.get("report_id") if isinstance(arguments, dict) else None
        if not raw_report_id:
            return ToolResult(False, "report_id is required")
        try:
            report_id = UUID(str(raw_report_id))
        except (TypeError, ValueError):
            return ToolResult(False, "report_id must be a valid UUID")
        context = await get_report_analysis_context(session, user_id, report_id)
        if context is None:
            return ToolResult(False, "报告不存在或无权访问")
        return ToolResult(True, _json.dumps(context, ensure_ascii=False), context)

    return ToolDefinition(
        name="report_tool",
        description=(
            "读取当前用户一份已解析完成的体检报告的原始结构化指标（报告信息、指标汇总、全部检查项目）。"
            "输入 report_id，返回只读 JSON 数据，不修改任何内容。仅当用户明确要求解读某份报告时使用。"
        ),
        parameters=REPORT_TOOL_SCHEMA,
        handler=handler,
    )
