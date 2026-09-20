"""Employee-owned consent, audit-log and explicit action-approval APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import get_current_user
from backend.app.core.database import get_db
from backend.app.models import AgentApproval, AuditLog, DataConsent
from backend.app.schemas.data_authorizations import (
    AccessLogResponse, ApprovalCreate, ApprovalDecision, ApprovalResponse,
    ConsentCreate, ConsentOverviewResponse, ConsentResponse, ConsentUpdate,
)
from backend.app.services.data_authorization_service import AuthorizationService, DATA_SCOPES


router = APIRouter(prefix="/data-authorizations", tags=["data-authorizations"])


def _consent(row: DataConsent) -> ConsentResponse:
    effective_status = "expired" if row.status == "active" and row.expires_at is not None and row.expires_at <= datetime.now(timezone.utc) else row.status
    return ConsentResponse(id=row.id, grantee_type=row.grantee_type, grantee_id=row.grantee_id, scope=row.scope, purpose=row.purpose, status=effective_status, granted_at=row.granted_at, expires_at=row.expires_at, revoked_at=row.revoked_at)


def _approval(row: AgentApproval) -> ApprovalResponse:
    return ApprovalResponse(id=row.id, action_type=row.action_type, action_payload=row.action_payload, status=row.status, requested_at=row.requested_at, decided_at=row.decided_at, expires_at=row.expires_at)


@router.get("/overview", response_model=ConsentOverviewResponse)
async def get_overview(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    return await AuthorizationService(session).overview(current_user.id)


@router.get("/scopes")
async def list_scopes(current_user=Depends(get_current_user)):
    # Static metadata only; no sensitive employee data is returned.
    return {"scopes": DATA_SCOPES}


@router.get("/consents", response_model=list[ConsentResponse])
async def list_consents(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    rows = list((await session.scalars(select(DataConsent).where(DataConsent.user_id == current_user.id).order_by(DataConsent.created_at.desc()))).all())
    return [_consent(row) for row in rows]


@router.post("/consents", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def grant_consent(payload: ConsentCreate, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    try:
        return _consent(await AuthorizationService(session).create_consent(user_id=current_user.id, payload=payload))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/consents/{consent_id}", response_model=ConsentResponse)
async def update_consent(consent_id: UUID, payload: ConsentUpdate, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    try:
        return _consent(await AuthorizationService(session).update(user_id=current_user.id, consent_id=consent_id, payload=payload))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/consents/{consent_id}/revoke", response_model=ConsentResponse)
async def revoke_consent(consent_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    try:
        return _consent(await AuthorizationService(session).revoke(user_id=current_user.id, consent_id=consent_id))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/access-logs", response_model=list[AccessLogResponse])
async def access_logs(limit: int = 30, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    capped_limit = max(1, min(limit, 100))
    rows = list((await session.scalars(select(AuditLog).where(
        AuditLog.resource_type == "data_authorization",
        AuditLog.details["user_id"].astext == str(current_user.id),
    ).order_by(AuditLog.created_at.desc()).limit(capped_limit))).all())
    return [AccessLogResponse(
        id=row.id,
        actor_type=(row.details or {}).get("actor_type", "system"),
        actor_id=(row.details or {}).get("actor_id"),
        scope=(row.details or {}).get("scope"),
        purpose=(row.details or {}).get("purpose"),
        action=row.action,
        outcome=row.outcome,
        created_at=row.created_at,
    ) for row in rows]


@router.get("/approvals", response_model=list[ApprovalResponse])
async def approvals(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    rows = list((await session.scalars(select(AgentApproval).where(AgentApproval.user_id == current_user.id).order_by(AgentApproval.requested_at.desc()))).all())
    return [_approval(row) for row in rows]


@router.post("/approvals", response_model=ApprovalResponse, status_code=status.HTTP_201_CREATED)
async def create_approval(payload: ApprovalCreate, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    row = AgentApproval(user_id=current_user.id, action_type=payload.action_type, action_payload=payload.action_payload, status="pending", requested_at=datetime.now(timezone.utc), expires_at=payload.expires_at)
    session.add(row)
    await AuthorizationService(session).audit(user_id=current_user.id, actor_type="user", actor_id=str(current_user.id), scope="health_service.booking.create" if payload.action_type == "health_service.booking.create" else None, purpose="高风险操作审批", action="approval.request", outcome="pending")
    await session.commit()
    await session.refresh(row)
    return _approval(row)


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_approval(approval_id: UUID, payload: ApprovalDecision, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    row = await session.get(AgentApproval, approval_id)
    if row is None or row.user_id != current_user.id:
        raise HTTPException(404, "审批记录不存在")
    if row.status != "pending":
        raise HTTPException(409, "该审批已处理")
    row.status, row.decided_at, row.decision_note = "approved", datetime.now(timezone.utc), payload.decision_note
    await AuthorizationService(session).audit(user_id=current_user.id, actor_type="user", actor_id=str(current_user.id), scope=None, purpose="高风险操作审批", action="approval.approve", outcome="allowed")
    await session.commit()
    await session.refresh(row)
    return _approval(row)
