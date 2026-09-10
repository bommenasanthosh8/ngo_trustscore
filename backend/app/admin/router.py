"""
Admin router — /admin and /api/v1/admin endpoints.
Handles administrative review, verification, and rejection of NGOs.
Note: For prototype purposes, NGO verification is performed by ADMIN without claiming government integration.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.auth.models import UserRole
from app.core.exceptions import ForbiddenException
from app.core.responses import ok
from app.dependencies import CurrentUserDep, DbDep, require_roles
from app.schemas.admin import AuditConfigUpdateRequest
from app.schemas.audit import ResolveDisputeRequest
from app.schemas.ngo import AdminRejectNGORequest, NGOResponse
from app.services import ngo_service

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_roles(UserRole.ADMIN.value))],
)


@router.get("/ngos/pending", response_model=dict)
async def get_pending_ngos(
    db: DbDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """
    Review all NGOs with PENDING verification status.
    Requires ADMIN privileges.
    """
    pending_ngos = await ngo_service.list_pending_ngos(db, skip=skip, limit=limit)
    return ok([NGOResponse.model_validate(n) for n in pending_ngos])


@router.post("/ngos/{id}/verify", response_model=dict)
async def verify_ngo(
    id: uuid.UUID,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Verify an NGO for the prototype platform.
    Requires ADMIN privileges.
    Sets verification_status to VERIFIED.
    """
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenException("Only platform administrators can verify an NGO.")

    verified = await ngo_service.verify_ngo(db, current_user, id)
    return ok(
        NGOResponse.model_validate(verified),
        message="NGO verified successfully by Administrator.",
    )


@router.post("/ngos/{id}/reject", response_model=dict)
async def reject_ngo(
    id: uuid.UUID,
    current_user: CurrentUserDep,
    db: DbDep,
    body: Optional[AdminRejectNGORequest] = None,
):
    """
    Reject an NGO onboarding application.
    Requires ADMIN privileges.
    Sets verification_status to REJECTED with optional administrative reason.
    """
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenException("Only platform administrators can reject an NGO.")

    reason = body.reason if body else None
    rejected = await ngo_service.reject_ngo(db, current_user, id, reason=reason)
    return ok(
        NGOResponse.model_validate(rejected),
        message="NGO onboarding rejected.",
    )


# ── Audit Configuration Management ───────────────────────────────────────────
@router.get("/audit-config", response_model=dict)
async def get_audit_configuration(
    current_user: CurrentUserDep,
):
    """
    Retrieve platform audit configuration thresholds.
    Requires ADMIN privileges.
    """
    from app.admin.service import get_audit_config
    config = get_audit_config()
    return ok(config.model_dump(mode="json"))


@router.put("/audit-config", response_model=dict)
async def update_audit_configuration(
    payload: AuditConfigUpdateRequest,
    current_user: CurrentUserDep,
):
    """
    Update runtime platform audit configuration thresholds.
    Requires ADMIN privileges.
    """
    from app.admin.service import update_audit_config
    config = update_audit_config(payload)
    return ok(config.model_dump(mode="json"), message="Audit configuration updated successfully.")


# ── Disputes Governance ───────────────────────────────────────────────────────
@router.get("/disputes", response_model=dict)
async def list_disputes(
    db: DbDep,
    current_user: CurrentUserDep,
    status: Optional[DisputeStatus] = Query(None, description="Filter by dispute status"),
):
    """
    List all project audit disputes across the platform.
    Requires ADMIN privileges.
    """
    from app.admin.service import list_all_disputes
    disputes = await list_all_disputes(db=db, status_filter=status)
    return ok([d.model_dump(mode="json") for d in disputes])


@router.post("/disputes/{id}/resolve", response_model=dict)
async def resolve_dispute_admin(
    id: uuid.UUID,
    payload: ResolveDisputeRequest,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Resolve an NGO audit dispute with administrative findings.
    Requires ADMIN privileges.
    """
    from app.audit import service as audit_service
    dispute = await audit_service.resolve_dispute(db, id, current_user, payload)
    return ok(dispute.model_dump(mode="json"), message="Dispute resolved successfully by Administrator.")


# ── System Activity Logs ──────────────────────────────────────────────────────
@router.get("/logs", response_model=dict)
async def get_activity_logs(
    db: DbDep,
    current_user: CurrentUserDep,
    action: Optional[str] = Query(None, description="Filter by action type"),
    actor_role: Optional[str] = Query(None, description="Filter by actor role"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Retrieve immutable system audit logs.
    Requires ADMIN privileges.
    """
    from app.admin.service import list_activity_logs
    logs = await list_activity_logs(
        db=db,
        action=action,
        actor_role=actor_role,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
    )
    return ok([l.model_dump(mode="json") for l in logs])


# ── System Statistics ─────────────────────────────────────────────────────────
@router.get("/stats", response_model=dict)
async def get_platform_statistics(
    db: DbDep,
    current_user: CurrentUserDep,
):
    """
    Retrieve platform-wide governance metrics and KPIs.
    Requires ADMIN privileges.
    """
    from app.admin.service import get_system_stats
    stats = await get_system_stats(db)
    return ok(stats.model_dump(mode="json"))
