"""
Audit Service Router.

Provides API endpoints for the audit queue, detailed dossiers, immutable auditor decisions,
and dispute resolution.
"""
from __future__ import annotations

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from app.audit import service
from app.core.responses import ok
from app.dependencies import CurrentUserDep, DbDep, require_roles
from app.models.enums import AuditSelectionReason, AuditStatus
from app.schemas.audit import (
    AuditDecisionCreateRequest,
    InitiateAuditRequest,
    ResolveDisputeRequest,
)

router = APIRouter(prefix="/audits", tags=["Independent Audit"])


@router.get("/health")
async def health():
    """Health check for audit service."""
    return ok({"status": "HEALTHY", "service": "Independent Audit Module"})


@router.get("", response_model=dict)
@router.get("/", response_model=dict, include_in_schema=False)
async def list_audit_queue(
    current_user: CurrentUserDep,
    db: DbDep,
    status: Optional[AuditStatus] = Query(None, description="Filter by audit status"),
    selection_reason: Optional[AuditSelectionReason] = Query(None, description="Filter by selection reason"),
):
    """
    List projects queued for independent audit.
    Restricted to platform auditors and administrators.
    Auto-populates cases from HIGH-RISK, HIGH-VALUE, and RANDOM SAMPLE triggers.
    """
    cases = await service.list_audits(
        db=db,
        user=current_user,
        status_filter=status,
        reason_filter=selection_reason,
    )
    return ok([c.model_dump(mode="json") for c in cases])


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_or_assign_audit(
    payload: InitiateAuditRequest,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Initiate or assign an audit case for a project.
    Restricted to platform auditors and administrators.
    """
    case = await service.initiate_audit(
        db=db,
        user=current_user,
        project_id=payload.project_id,
        scope=payload.scope,
        selection_reason=payload.selection_reason or AuditSelectionReason.MANUAL_ASSIGNMENT,
    )
    return ok(case.model_dump(mode="json"), message="Audit case successfully created.")


@router.get("/dashboard-queues", response_model=dict)
async def get_dashboard_queues(
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Retrieve audit cases partitioned into the 6 operational queues:
    1. Pending audits
    2. High-risk projects
    3. High-value projects
    4. Random audit queue
    5. Disputed projects
    6. Recently verified projects
    """
    queues = await service.get_categorized_audit_queues(db=db, user=current_user)
    return ok(queues.model_dump(mode="json"))


@router.get("/{id}", response_model=dict)
async def get_audit_dossier(
    id: uuid.UUID,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Retrieve comprehensive audit dossier for a project.
    Includes:
    - Project details, location, and geofence
    - NGO claim
    - Evidence timeline with full files & cryptographic hashes
    - Financial documentation & consistency variance report
    - 10-point Verification Engine results
    - Risk assessment narrative reasons
    - Historical decisions & active disputes
    """
    dossier = await service.get_audit_dossier(db, id, current_user)
    return ok(dossier.model_dump(mode="json"))


@router.get("/{id}/integrity-flags", response_model=dict)
async def get_audit_integrity_flags(
    id: uuid.UUID,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Retrieve comprehensive 10-threat anti-manipulation integrity report and active flags
    for the project associated with this audit case.
    Restricted to assigned Auditor, Admin, or project owning NGO.
    """
    from app.auth.models import UserRole
    from app.core.exceptions import ForbiddenException
    from app.models.audit import Audit
    from app.projects.service import get_project_by_id
    from app.risk.integrity_service import get_integrity_service

    audit = await db.get(Audit, id)
    if not audit:
        # Fallback: maybe id is project_id
        project = await get_project_by_id(db, str(id))
    else:
        project = await get_project_by_id(db, str(audit.project_id))

    if current_user.role == UserRole.DONOR:
        raise ForbiddenException("Donors do not have access to audit integrity flags.")
    if current_user.role == UserRole.NGO and project.ngo_id != current_user.ngo_id:
        raise ForbiddenException("You do not have permission to view audit integrity flags for this project.")

    service_inst = get_integrity_service()
    report = await service_inst.generate_project_integrity_report(db, project)
    return ok(report.model_dump(mode="json"))


@router.post("/{id}/decision", response_model=dict, status_code=status.HTTP_201_CREATED)
async def record_audit_decision(
    id: uuid.UUID,
    payload: AuditDecisionCreateRequest,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Record an immutable auditor decision:
    - CONFIRMED
    - PARTIALLY_CONFIRMED
    - REJECTED
    - DISCREPANCY

    Auditor decisions are immutable. If a decision needs correction,
    a new review record is created that links and supersedes the previous decision.
    NGO users are strictly forbidden from modifying or submitting decisions.
    """
    decision = await service.record_audit_decision(db, id, current_user, payload)
    return ok(
        decision.model_dump(mode="json"),
        message="Audit decision recorded immutably.",
    )


@router.post("/disputes/{id}/resolve", response_model=dict)
async def resolve_dispute_endpoint(
    id: uuid.UUID,
    payload: ResolveDisputeRequest,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Resolve an NGO audit dispute.
    Restricted to platform administrators and auditors.
    """
    dispute = await service.resolve_dispute(db, id, current_user, payload)
    return ok(
        dispute.model_dump(mode="json"),
        message="Dispute resolved successfully.",
    )


@router.get("/logs", response_model=dict)
async def get_audit_activity_logs(
    db: DbDep,
    current_user: CurrentUserDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Retrieve activity logs for the auditor dashboard.
    Restricted to auditors and platform administrators.
    """
    from app.admin.service import list_activity_logs
    logs = await list_activity_logs(db=db, limit=limit, offset=offset)
    return ok([l.model_dump(mode="json") for l in logs])


# Compatibility alias router for /audit/cases
audit_cases_router = APIRouter(prefix="/audit", tags=["Independent Audit"])


@audit_cases_router.get("/cases", response_model=dict, dependencies=[Depends(require_roles("AUDITOR", "ADMIN"))])
@audit_cases_router.get("/cases/", response_model=dict, include_in_schema=False, dependencies=[Depends(require_roles("AUDITOR", "ADMIN"))])
async def list_audit_cases_compat():
    """Compatibility endpoint for audit cases list."""
    return ok([], message="Audit cases retrieved successfully.")

