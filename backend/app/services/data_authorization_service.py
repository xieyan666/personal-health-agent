"""Scope-level authorization, revocation and privacy-preserving audit helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import AgentApproval, AuditLog, DataConsent


DATA_SCOPES = [
    {"code": "health_profile.read", "name": "健康档案", "category": "health"},
    {"code": "wearable.sleep.read", "name": "睡眠数据", "category": "wearable"},
    {"code": "wearable.exercise.read", "name": "运动数据", "category": "wearable"},
    {"code": "wearable.heart_rate.read", "name": "心率数据", "category": "wearable"},
    {"code": "health_report.read", "name": "体检报告", "category": "health"},
    {"code": "health_risk.read", "name": "健康风险", "category": "health"},
    {"code": "health_plan.read", "name": "健康计划读取", "category": "health"},
    {"code": "health_plan.write", "name": "健康计划写入", "category": "health"},
    {"code": "mental_checkin.read", "name": "心理打卡", "category": "mental", "sensitive": True},
    {"code": "mental_assessment.read", "name": "心理测评", "category": "mental", "sensitive": True},
    {"code": "mental_trend.read", "name": "心理趋势", "category": "mental", "sensitive": True},
    {"code": "health_service.read", "name": "健康服务", "category": "service"},
    {"code": "health_service.booking.create", "name": "健康服务预约", "category": "service"},
]
SCOPE_CODES = {item["code"] for item in DATA_SCOPES}
MENTAL_SCOPES = {item["code"] for item in DATA_SCOPES if item.get("sensitive")}

AGENT_SCOPE_MAP = {
    "health_supervisor_agent": {"health_profile.read", "health_risk.read", "health_plan.read"},
    "sleep_agent": {"wearable.sleep.read", "health_profile.read"},
    "nutrition_agent": {"health_profile.read", "health_report.read"},
    "fitness_agent": {"wearable.exercise.read", "wearable.heart_rate.read", "health_profile.read"},
    "report_agent": {"health_report.read", "health_profile.read"},
    "risk_agent": {"health_profile.read", "wearable.sleep.read", "wearable.exercise.read", "wearable.heart_rate.read", "health_report.read"},
    "health_plan_agent": {"health_profile.read", "health_risk.read", "health_plan.read", "health_plan.write"},
    "mental_health_agent": {"mental_checkin.read", "mental_assessment.read", "mental_trend.read"},
    "health_service_agent": {"health_profile.read", "health_risk.read", "health_plan.read", "health_service.read", "health_service.booking.create"},
}
# The persisted first-party slug is ``health_supervisor``; retain the legacy
# consent identifier used by older tools and existing user grants.
AGENT_SCOPE_MAP["health_supervisor"] = AGENT_SCOPE_MAP["health_supervisor_agent"]


class DataAccessNotAuthorized(Exception):
    """Raised at a tool/service boundary before sensitive data is read."""

    code = "DATA_ACCESS_NOT_AUTHORIZED"

    def __init__(self, scope: str):
        super().__init__(f"DATA_ACCESS_NOT_AUTHORIZED:{scope}")
        self.scope = scope


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthorizationService:
    """Central authorization service; callers never inspect consent rows directly."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def audit(self, *, user_id: UUID, actor_type: str, actor_id: str | None, scope: str | None, purpose: str | None, action: str, outcome: str) -> None:
        # Do not include health values, prompts or report contents in this audit event.
        self.session.add(AuditLog(
            actor_user_id=user_id if actor_type == "user" else None,
            action=action,
            resource_type="data_authorization",
            resource_id=None,
            risk_level="high" if scope in MENTAL_SCOPES else "medium",
            safety_status="authorized" if outcome == "allowed" else "denied",
            outcome=outcome,
            details={"actor_type": actor_type, "actor_id": actor_id, "user_id": str(user_id), "scope": scope, "purpose": purpose},
        ))

    async def is_authorized(self, *, user_id: UUID, grantee_type: str, grantee_id: str, scope: str) -> bool:
        now = utcnow()
        acceptable_types = [grantee_type]
        if grantee_id == "health_service_agent":
            # Service-consent records are granted to the booking/recommendation boundary.
            acceptable_types.append("service")
        query = select(DataConsent.id).where(
            DataConsent.user_id == user_id,
            DataConsent.grantee_type.in_(acceptable_types),
            DataConsent.scope == scope,
            DataConsent.status == "active",
            or_(DataConsent.expires_at.is_(None), DataConsent.expires_at > now),
            # The supervisor is the deliberate umbrella consent for non-mental specialist agents.
            DataConsent.grantee_id.in_([grantee_id, "health_supervisor_agent"]),
        )
        if scope in MENTAL_SCOPES:
            query = query.where(DataConsent.grantee_id == grantee_id)
        return (await self.session.scalar(query)) is not None

    async def require(self, *, user_id: UUID, grantee_type: str, grantee_id: str, scope: str, purpose: str) -> None:
        allowed = await self.is_authorized(user_id=user_id, grantee_type=grantee_type, grantee_id=grantee_id, scope=scope)
        await self.audit(user_id=user_id, actor_type=grantee_type, actor_id=grantee_id, scope=scope, purpose=purpose, action="data.access", outcome="allowed" if allowed else "denied")
        await self.session.commit()
        if not allowed:
            # Security alerts bypass the per-type preference so a disabled
            # notification toggle never silences access-control warnings.
            from backend.app.services.notification_service import create_notification
            await create_notification(
                self.session,
                user_id,
                "authorization",
                "数据访问被阻止",
                "未授权的数据访问请求已被系统阻止，可前往数据授权页面查看与管理授权。",
                "/employee/authorization",
                force=True,
            )
            raise DataAccessNotAuthorized(scope)

    async def create_consent(self, *, user_id: UUID, payload) -> DataConsent:
        if payload.scope not in SCOPE_CODES:
            raise ValueError("不支持的数据授权范围")
        now = utcnow()
        existing = await self.session.scalar(select(DataConsent).where(
            DataConsent.user_id == user_id,
            DataConsent.grantee_type == payload.grantee_type,
            DataConsent.grantee_id == payload.grantee_id,
            DataConsent.scope == payload.scope,
        ).order_by(DataConsent.created_at.desc()))
        if existing:
            existing.purpose, existing.expires_at, existing.status, existing.granted_at, existing.revoked_at = payload.purpose, payload.expires_at, "active", now, None
            consent = existing
        else:
            consent = DataConsent(user_id=user_id, grantee_type=payload.grantee_type, grantee_id=payload.grantee_id, scope=payload.scope, purpose=payload.purpose, status="active", granted_at=now, expires_at=payload.expires_at)
            self.session.add(consent)
        await self.audit(user_id=user_id, actor_type="user", actor_id=str(user_id), scope=payload.scope, purpose=payload.purpose, action="consent.grant", outcome="allowed")
        await self.session.commit()
        await self.session.refresh(consent)
        return consent

    async def revoke(self, *, user_id: UUID, consent_id: UUID) -> DataConsent:
        consent = await self.session.get(DataConsent, consent_id)
        if consent is None or consent.user_id != user_id:
            raise LookupError("授权记录不存在")
        consent.status, consent.revoked_at = "revoked", utcnow()
        await self.audit(user_id=user_id, actor_type="user", actor_id=str(user_id), scope=consent.scope, purpose=consent.purpose, action="consent.revoke", outcome="allowed")
        await self.session.commit()
        await self.session.refresh(consent)
        return consent

    async def update(self, *, user_id: UUID, consent_id: UUID, payload) -> DataConsent:
        consent = await self.session.get(DataConsent, consent_id)
        if consent is None or consent.user_id != user_id:
            raise LookupError("授权记录不存在")
        if payload.purpose is not None:
            consent.purpose = payload.purpose
        consent.expires_at = payload.expires_at
        await self.session.commit()
        await self.session.refresh(consent)
        return consent

    async def overview(self, user_id: UUID) -> dict:
        now = utcnow()
        active = and_(DataConsent.user_id == user_id, DataConsent.status == "active", or_(DataConsent.expires_at.is_(None), DataConsent.expires_at > now))
        count = await self.session.scalar(select(func.count(DataConsent.id)).where(active)) or 0
        ai_count = await self.session.scalar(select(func.count(DataConsent.id)).where(active, DataConsent.grantee_type == "agent")) or 0
        service_count = await self.session.scalar(select(func.count(DataConsent.id)).where(active, DataConsent.grantee_type == "service")) or 0
        scopes = list((await self.session.scalars(select(DataConsent.scope).where(active))).all())
        last_access = await self.session.scalar(select(AuditLog.created_at).where(AuditLog.resource_type == "data_authorization", AuditLog.details["user_id"].astext == str(user_id), AuditLog.action == "data.access", AuditLog.outcome == "allowed").order_by(AuditLog.created_at.desc()).limit(1))
        pending = await self.session.scalar(select(func.count(AgentApproval.id)).where(AgentApproval.user_id == user_id, AgentApproval.status == "pending")) or 0
        return {"active_consent_count": count, "active_scope_count": len(set(scopes)), "ai_consent_count": ai_count, "service_consent_count": service_count, "mental_scope_enabled": any(scope in MENTAL_SCOPES for scope in scopes), "last_access_at": last_access, "pending_approval_count": pending}
