"""
Independent Audit Service.

Manages risk-based audit queue selection, comprehensive dossier compilation,
immutable auditor decisions, dispute workflows, and immutable activity auditing.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.activity import ActivityLog
from app.models.audit import Audit, AuditDecision
from app.models.dispute import Dispute
from app.models.enums import (
    AuditDecisionType,
    AuditSelectionReason,
    AuditStatus,
    DisputeStatus,
    ProjectStatus,
    UserRole,
)
from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence
from app.models.ngo import NGO
from app.models.project import Project
from app.models.user import User
from app.projects.service import get_project_by_id as resolve_project
from app.risk.engine import get_risk_engine
from app.schemas.audit import (
    AuditDecisionCreateRequest,
    AuditDecisionResponse,
    AuditDossierResponse,
    AuditQueueGroupResponse,
    AuditSummaryResponse,
    CreateDisputeRequest,
    DisputeResponse,
    ResolveDisputeRequest,
)
from app.schemas.evidence import EvidenceTimelineItem
from app.services.evidence_service import _serialize_evidence
from app.services.financial_evidence_service import (
    _serialize_financial_evidence,
    calculate_financial_consistency,
)
from app.verification.engine import get_verification_engine

logger = logging.getLogger(__name__)


async def _log_audit_activity(
    db: AsyncSession,
    user: Optional[User],
    action: str,
    resource_type: str,
    resource_id: str,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """Helper to log immutable audit event to ActivityLog."""
    log = ActivityLog(
        action=action,
        actor_id=user.id if user else None,
        actor_role=user.role.value if user else None,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        success=True,
    )
    db.add(log)


async def populate_audit_queue_for_project(
    db: AsyncSession,
    project: Project,
    auditor: User,
) -> Optional[Audit]:
    """
    Evaluates project risk and value thresholds to determine if the project
    should be queued for independent audit.
    Criteria:
    1. HIGH-RISK (Risk score >= 60)
    2. HIGH-VALUE (Budget >= 1,000,000)
    3. RANDOM SAMPLE (5% sampling rate)
    """
    settings = get_settings()

    # Check if an active audit already exists
    existing_q = select(Audit).where(Audit.project_id == project.id)
    existing_res = await db.execute(existing_q)
    existing_audit = existing_res.scalars().first()
    if existing_audit:
        return existing_audit

    # Evaluate risk
    risk_engine = get_risk_engine()
    risk_report = await risk_engine.evaluate_project_risk(db, project)

    selection_reason: Optional[AuditSelectionReason] = None
    if risk_report.risk_level == "HIGH" or risk_report.risk_score >= 60.0:
        selection_reason = AuditSelectionReason.HIGH_RISK
    elif float(project.target_amount or 0.0) >= settings.HIGH_PROJECT_VALUE_THRESHOLD:
        selection_reason = AuditSelectionReason.HIGH_VALUE
    else:
        # Check deterministic pseudo-random sampling
        sample_hash = int(hashlib.md5(str(project.id).encode()).hexdigest()[:8], 16)
        if (sample_hash % 100) < int(settings.AUDIT_RANDOM_SAMPLE_RATE * 100):
            selection_reason = AuditSelectionReason.RANDOM_SAMPLE

    if not selection_reason:
        return None

    audit = Audit(
        project_id=project.id,
        auditor_id=auditor.id,
        selection_reason=selection_reason,
        status=AuditStatus.INITIATED,
        scope=f"Audit queued due to {selection_reason.value} trigger.",
    )
    db.add(audit)
    await db.flush()

    await _log_audit_activity(
        db=db,
        user=auditor,
        action="AUDIT_QUEUED",
        resource_type="audit",
        resource_id=str(audit.id),
        detail={
            "project_id": str(project.id),
            "project_code": project.project_code,
            "selection_reason": selection_reason.value,
            "risk_score": risk_report.risk_score,
        },
    )
    await db.commit()
    await db.refresh(audit)
    return audit


async def list_audits(
    db: AsyncSession,
    user: User,
    status_filter: Optional[AuditStatus] = None,
    reason_filter: Optional[AuditSelectionReason] = None,
) -> List[AuditSummaryResponse]:
    """List audit cases in queue. Restricted to AUDITOR and ADMIN."""
    if user.role not in (UserRole.AUDITOR, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to platform auditors and administrators.",
        )

    # Automatically scan projects and populate queue
    proj_query = select(Project).where(Project.status != ProjectStatus.VERIFIED)
    proj_res = await db.execute(proj_query)
    unverified_projects = proj_res.scalars().all()
    for p in unverified_projects:
        await populate_audit_queue_for_project(db, p, user)

    # Fetch audit records with eager loaded relationships
    q = (
        select(Audit)
        .options(
            selectinload(Audit.project).selectinload(Project.ngo),
            selectinload(Audit.auditor),
            selectinload(Audit.decisions),
        )
        .order_by(Audit.created_at.desc())
    )
    if status_filter:
        q = q.where(Audit.status == status_filter)
    if reason_filter:
        q = q.where(Audit.selection_reason == reason_filter)

    result = await db.execute(q)
    audits = result.scalars().all()

    summaries: List[AuditSummaryResponse] = []
    risk_engine = get_risk_engine()

    for a in audits:
        p = a.project
        latest_dec = next((d.decision for d in a.decisions if not d.is_superseded), None)
        risk_rep = await risk_engine.evaluate_project_risk(db, p)

        summaries.append(
            AuditSummaryResponse(
                id=a.id,
                project_id=p.id,
                project_code=p.project_code,
                project_title=p.title,
                project_category=p.project_type,
                project_status=p.status,
                target_amount=float(p.target_amount or 0.0),
                ngo_id=p.ngo_id,
                ngo_name=p.ngo.name if p.ngo else None,
                auditor_id=a.auditor_id,
                auditor_name=a.auditor.full_name if a.auditor else None,
                status=a.status,
                selection_reason=a.selection_reason,
                risk_score=risk_rep.risk_score,
                risk_level=risk_rep.risk_level.value,
                created_at=a.created_at,
                latest_decision=latest_dec,
            )
        )

    return summaries


async def initiate_audit(
    db: AsyncSession,
    user: User,
    project_id: uuid.UUID,
    scope: Optional[str] = None,
    selection_reason: AuditSelectionReason = AuditSelectionReason.MANUAL_ASSIGNMENT,
) -> AuditSummaryResponse:
    """Initiate or assign an audit for a project manually or from priority triage."""
    if user.role not in (UserRole.AUDITOR, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to platform auditors and administrators.",
        )

    q = select(Project).options(selectinload(Project.ngo)).where(Project.id == project_id)
    res = await db.execute(q)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    # Check if an active audit already exists
    existing_q = (
        select(Audit)
        .options(
            selectinload(Audit.project).selectinload(Project.ngo),
            selectinload(Audit.auditor),
            selectinload(Audit.decisions),
        )
        .where(Audit.project_id == project_id)
    )
    existing_res = await db.execute(existing_q)
    existing_audit = existing_res.scalars().first()
    if existing_audit:
        risk_engine = get_risk_engine()
        risk_rep = await risk_engine.evaluate_project_risk(db, existing_audit.project)
        latest_dec = next((d.decision for d in existing_audit.decisions if not d.is_superseded), None)
        return AuditSummaryResponse(
            id=existing_audit.id,
            project_id=project.id,
            project_code=project.project_code,
            project_title=project.title,
            project_category=project.project_type,
            project_status=project.status,
            target_amount=float(project.target_amount or 0.0),
            ngo_id=project.ngo_id,
            ngo_name=project.ngo.name if project.ngo else None,
            auditor_id=existing_audit.auditor_id,
            auditor_name=existing_audit.auditor.full_name if existing_audit.auditor else None,
            status=existing_audit.status,
            selection_reason=existing_audit.selection_reason,
            risk_score=risk_rep.risk_score,
            risk_level=risk_rep.risk_level.value,
            created_at=existing_audit.created_at,
            latest_decision=latest_dec,
        )

    audit = Audit(
        project_id=project.id,
        auditor_id=user.id,
        selection_reason=selection_reason,
        status=AuditStatus.INITIATED,
        scope=scope or f"Independent audit initiated by {user.full_name or 'Auditor'}.",
    )
    db.add(audit)
    await db.flush()

    await _log_audit_activity(
        db=db,
        user=user,
        action="AUDIT_INITIATED",
        resource_type="audit",
        resource_id=str(audit.id),
        detail={
            "project_id": str(project.id),
            "project_code": project.project_code,
            "selection_reason": selection_reason.value,
        },
    )
    await db.commit()

    risk_engine = get_risk_engine()
    risk_rep = await risk_engine.evaluate_project_risk(db, project)

    return AuditSummaryResponse(
        id=audit.id,
        project_id=project.id,
        project_code=project.project_code,
        project_title=project.title,
        project_category=project.project_type,
        project_status=project.status,
        target_amount=float(project.target_amount or 0.0),
        ngo_id=project.ngo_id,
        ngo_name=project.ngo.name if project.ngo else None,
        auditor_id=audit.auditor_id,
        auditor_name=user.full_name,
        status=audit.status,
        selection_reason=audit.selection_reason,
        risk_score=risk_rep.risk_score,
        risk_level=risk_rep.risk_level.value,
        created_at=audit.created_at,
        latest_decision=None,
    )


async def get_categorized_audit_queues(
    db: AsyncSession,
    user: User,
) -> AuditQueueGroupResponse:
    """
    Retrieve all audit queues categorized into distinct operational buckets:
    1. Pending audits (INITIATED or IN_PROGRESS)
    2. High-risk projects (HIGH_RISK or risk_score >= 60)
    3. High-value projects (HIGH_VALUE or budget >= 1,000,000)
    4. Random audit queue (RANDOM_SAMPLE)
    5. Disputed projects (DISPUTED)
    6. Recently verified projects (VERIFIED or CONCLUDED)
    """
    all_audits = await list_audits(db=db, user=user)

    pending: List[AuditSummaryResponse] = []
    high_risk: List[AuditSummaryResponse] = []
    high_value: List[AuditSummaryResponse] = []
    random_q: List[AuditSummaryResponse] = []
    disputed: List[AuditSummaryResponse] = []
    recently_verified: List[AuditSummaryResponse] = []

    for a in all_audits:
        # 1. Pending
        if a.status in (AuditStatus.INITIATED, AuditStatus.IN_PROGRESS):
            pending.append(a)

        # 2. High-risk
        if a.selection_reason == AuditSelectionReason.HIGH_RISK or (a.risk_score and a.risk_score >= 60.0):
            high_risk.append(a)

        # 3. High-value
        if a.selection_reason == AuditSelectionReason.HIGH_VALUE or a.target_amount >= 1000000.0:
            high_value.append(a)

        # 4. Random sample
        if a.selection_reason == AuditSelectionReason.RANDOM_SAMPLE:
            random_q.append(a)

        # 5. Disputed
        if a.status == AuditStatus.DISPUTED or a.project_status == ProjectStatus.DISPUTED:
            disputed.append(a)

        # 6. Recently verified
        if a.project_status in (ProjectStatus.VERIFIED, ProjectStatus.PARTIALLY_VERIFIED) or a.status == AuditStatus.CONCLUDED:
            recently_verified.append(a)

    return AuditQueueGroupResponse(
        pending_audits=pending,
        high_risk=high_risk,
        high_value=high_value,
        random_queue=random_q,
        disputed=disputed,
        recently_verified=recently_verified,
        counts={
            "pending_audits": len(pending),
            "high_risk": len(high_risk),
            "high_value": len(high_value),
            "random_queue": len(random_q),
            "disputed": len(disputed),
            "recently_verified": len(recently_verified),
            "total_all": len(all_audits),
        },
    )


async def get_audit_dossier(
    db: AsyncSession,
    audit_id: uuid.UUID,
    user: User,
) -> AuditDossierResponse:
    """
    Assemble the complete multi-vector audit dossier for an auditor/admin.
    """
    if user.role not in (UserRole.AUDITOR, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to platform auditors and administrators.",
        )

    q = (
        select(Audit)
        .options(
            selectinload(Audit.project).selectinload(Project.ngo),
            selectinload(Audit.decisions),
        )
        .where(Audit.id == audit_id)
    )
    res = await db.execute(q)
    audit = res.scalars().first()
    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit case {audit_id} not found.",
        )

    project = audit.project

    # Enforce auditor assignment authorization: if assigned to a specific auditor, others cannot view unless ADMIN
    if user.role == UserRole.AUDITOR and audit.auditor_id is not None and str(audit.auditor_id) != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: This audit case is assigned to another auditor.",
        )

    # 1. Fetch evidence items & serialize timeline
    ev_q = (
        select(Evidence)
        .options(selectinload(Evidence.submitted_by))
        .where(Evidence.project_id == project.id)
        .order_by(Evidence.uploaded_at.asc())
    )
    ev_res = await db.execute(ev_q)
    evidences = ev_res.scalars().all()

    timeline_items = [
        EvidenceTimelineItem(
            id=e.id,
            title=e.title,
            evidence_type=e.evidence_type,
            description=e.description,
            original_filename=e.original_filename,
            file_hash_sha256=e.file_hash_sha256,
            captured_at=e.captured_at,
            uploaded_at=e.uploaded_at,
            effective_timestamp=e.captured_at or e.uploaded_at,
            location_status=e.location_status,
            latitude=e.latitude,
            longitude=e.longitude,
            gps_accuracy=e.gps_accuracy,
            verification_status=e.verification_status,
            supersedes_id=e.supersedes_id,
            is_revision=bool(e.supersedes_id),
            uploader_name=e.submitted_by.full_name if e.submitted_by else None,
        )
        for e in evidences
    ]

    # 2. Fetch financial evidence & report
    fin_q = (
        select(FinancialEvidence)
        .options(selectinload(FinancialEvidence.submitted_by))
        .where(FinancialEvidence.project_id == project.id)
        .order_by(FinancialEvidence.uploaded_at.asc())
    )
    fin_res = await db.execute(fin_q)
    financials = fin_res.scalars().all()
    fin_serialized = [_serialize_financial_evidence(f) for f in financials]
    fin_report = calculate_financial_consistency(project, financials)

    # 3. Verification Report (10-point check results)
    ver_engine = get_verification_engine()
    ver_report = await ver_engine.verify_project(db, project)

    # 4. Risk Assessment Report
    risk_engine = get_risk_engine()
    risk_rep = await risk_engine.evaluate_project_risk(db, project)

    # 5. Decisions History
    decisions_history = [
        AuditDecisionResponse(
            id=d.id,
            audit_id=d.audit_id,
            decision=d.decision,
            findings=d.findings,
            notes=d.notes,
            supporting_evidence=d.supporting_evidence,
            is_superseded=d.is_superseded,
            superseded_by_id=d.superseded_by_id,
            decided_by_id=d.decided_by_id,
            decided_at=d.decided_at,
        )
        for d in audit.decisions
    ]

    # 6. Disputes
    disp_q = select(Dispute).where(Dispute.project_id == project.id)
    disp_res = await db.execute(disp_q)
    disputes = disp_res.scalars().all()
    disputes_serialized = [
        DisputeResponse(
            id=d.id,
            project_id=d.project_id,
            project_code=project.project_code,
            raised_by_id=d.raised_by_id,
            reason=d.reason,
            status=d.status,
            resolution_notes=d.resolution_notes,
            created_at=d.created_at,
        )
        for d in disputes
    ]

    # 7. Authoritative Evidence Score
    ev_score = None
    ev_status = None
    ev_breakdown = None
    try:
        from app.scores.service import get_or_calculate_project_score
        score_resp = await get_or_calculate_project_score(db, str(project.id))
        ev_score = score_resp.final_score
        ev_status = score_resp.status.value if hasattr(score_resp.status, 'value') else str(score_resp.status)
        ev_breakdown = {k: v.model_dump() for k, v in score_resp.factors.items()}
    except Exception as err:
        logger.warning(f"Could not load project score for audit dossier: {err}")

    # 8. Anti-manipulation integrity report
    integrity_rep = None
    try:
        from app.risk.integrity_service import get_integrity_service
        integrity_svc = get_integrity_service()
        integrity_rep = await integrity_svc.generate_project_integrity_report(db, project)
    except Exception as err:
        logger.warning(f"Could not generate integrity report for audit dossier: {err}")

    return AuditDossierResponse(
        audit_id=audit.id,
        status=audit.status,
        selection_reason=audit.selection_reason,
        created_at=audit.created_at,
        scope=audit.scope,
        project_id=project.id,
        project_code=project.project_code,
        project_title=project.title,
        project_category=project.project_type,
        verification_model=project.verification_model,
        project_status=project.status,
        location_name=project.location_name,
        latitude=float(project.latitude) if project.latitude else None,
        longitude=float(project.longitude) if project.longitude else None,
        geofence_radius=float(project.geofence_radius or 500.0),
        ngo_id=project.ngo_id,
        ngo_name=project.ngo.name if project.ngo else "Unknown NGO",
        target_amount=float(project.target_amount or 0.0),
        total_budget=float(project.total_budget or 0.0),
        expected_beneficiaries=project.expected_beneficiaries or 0,
        project_description=project.description,
        start_date=project.start_date,
        expected_completion_date=project.end_date,
        evidence_timeline=timeline_items,
        financial_evidence=fin_serialized,
        financial_consistency=fin_report,
        verification_report=ver_report,
        risk_assessment=risk_rep,
        evidence_score=ev_score,
        evidence_score_status=ev_status,
        evidence_score_breakdown=ev_breakdown,
        decisions_history=decisions_history,
        disputes=disputes_serialized,
        integrity_report=integrity_rep,
    )


async def record_audit_decision(
    db: AsyncSession,
    audit_id: uuid.UUID,
    user: User,
    payload: AuditDecisionCreateRequest,
) -> AuditDecisionResponse:
    """
    Submit an immutable audit decision.
    - Restricted to AUDITOR and ADMIN. NGO cannot submit or edit decisions.
    - If a previous decision exists, it is marked superseded and a new review
      record is linked rather than overwriting history.
    - Updates Project and Audit status.
    - Creates persistent ActivityLog entry.
    """
    if user.role not in (UserRole.AUDITOR, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: NGO users cannot make or modify audit decisions.",
        )

    if not payload.findings or len(payload.findings.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Auditor findings/reason is required before submitting a decision.",
        )

    q = (
        select(Audit)
        .options(selectinload(Audit.project), selectinload(Audit.decisions))
        .where(Audit.id == audit_id)
    )
    res = await db.execute(q)
    audit = res.scalars().first()
    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit case {audit_id} not found.",
        )

    project = audit.project

    # Enforce assigned auditor access: if assigned to another auditor, reject unless ADMIN
    if user.role == UserRole.AUDITOR and audit.auditor_id is not None and str(audit.auditor_id) != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: This audit case is assigned to another auditor. Only the assigned auditor or an administrator can record a decision.",
        )
    # If unassigned, assign this auditor to the case
    if audit.auditor_id is None:
        audit.auditor_id = user.id

    # Find any active prior decision
    prior_decision = next((d for d in audit.decisions if not d.is_superseded), None)

    # Create new immutable decision
    now_utc = datetime.now(timezone.utc)
    new_decision = AuditDecision(
        audit_id=audit.id,
        decision=payload.decision,
        findings=payload.findings,
        notes=payload.notes,
        supporting_evidence=payload.supporting_evidence,
        is_superseded=False,
        decided_by_id=user.id,
        decided_at=now_utc,
    )
    db.add(new_decision)
    await db.flush()

    # If prior decision existed, mark it superseded and link it
    if prior_decision:
        prior_decision.is_superseded = True
        prior_decision.superseded_by_id = new_decision.id

    # Update project and audit status
    audit.status = AuditStatus.CONCLUDED
    audit.findings = payload.findings

    if payload.decision == AuditDecisionType.CONFIRMED:
        project.status = ProjectStatus.VERIFIED
    elif payload.decision == AuditDecisionType.PARTIALLY_CONFIRMED:
        project.status = ProjectStatus.PARTIALLY_VERIFIED
    elif payload.decision == AuditDecisionType.DISCREPANCY:
        project.status = ProjectStatus.DISPUTED
    elif payload.decision == AuditDecisionType.REJECTED:
        project.status = ProjectStatus.UNDER_VERIFICATION

    # Log immutable activity event
    await _log_audit_activity(
        db=db,
        user=user,
        action="AUDIT_DECISION_RECORDED",
        resource_type="audit",
        resource_id=str(audit.id),
        detail={
            "decision": payload.decision.value,
            "project_id": str(project.id),
            "project_code": project.project_code,
            "is_superseding": bool(prior_decision),
            "prior_decision_id": str(prior_decision.id) if prior_decision else None,
        },
    )

    # Recalculate project evidence score
    try:
        from app.scores.engine import get_score_engine
        score_engine = get_score_engine()
        await score_engine.calculate_score(db, project, record_snapshot=True)
    except Exception as exc:
        logger.warning(f"Could not update score snapshot on audit decision: {exc}")

    await db.commit()
    await db.refresh(new_decision)

    return AuditDecisionResponse(
        id=new_decision.id,
        audit_id=new_decision.audit_id,
        decision=new_decision.decision,
        findings=new_decision.findings,
        notes=new_decision.notes,
        supporting_evidence=new_decision.supporting_evidence,
        is_superseded=new_decision.is_superseded,
        superseded_by_id=new_decision.superseded_by_id,
        decided_by_id=new_decision.decided_by_id,
        decided_at=new_decision.decided_at,
    )


async def create_project_dispute(
    db: AsyncSession,
    project_identifier: str | uuid.UUID,
    user: User,
    payload: CreateDisputeRequest,
) -> DisputeResponse:
    """
    NGO requests review of an audit decision for their project.
    Sets project and audit status to DISPUTED and creates an ActivityLog.
    """
    project = await resolve_project(db, project_identifier)

    # Authorization: User must be NGO that owns the project or admin
    if user.role == UserRole.NGO and user.ngo_id != project.ngo_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You can only raise disputes for projects owned by your NGO.",
        )

    dispute = Dispute(
        project_id=project.id,
        raised_by_id=user.id,
        reason=payload.reason,
        status=DisputeStatus.OPEN,
    )
    db.add(dispute)

    # Move project and active audits to DISPUTED
    project.status = ProjectStatus.DISPUTED

    audits_q = select(Audit).where(Audit.project_id == project.id)
    audits_res = await db.execute(audits_q)
    for a in audits_res.scalars().all():
        a.status = AuditStatus.DISPUTED

    await db.flush()

    await _log_audit_activity(
        db=db,
        user=user,
        action="DISPUTE_RAISED",
        resource_type="project",
        resource_id=str(project.id),
        detail={
            "dispute_id": str(dispute.id),
            "project_code": project.project_code,
            "reason_preview": payload.reason[:200],
        },
    )

    # Recalculate project evidence score reflecting active dispute
    try:
        from app.scores.engine import get_score_engine
        score_engine = get_score_engine()
        await score_engine.calculate_score(db, project, record_snapshot=True)
    except Exception as exc:
        logger.warning(f"Could not update score snapshot on dispute creation: {exc}")

    await db.commit()
    await db.refresh(dispute)

    return DisputeResponse(
        id=dispute.id,
        project_id=project.id,
        project_code=project.project_code,
        raised_by_id=dispute.raised_by_id,
        reason=dispute.reason,
        status=dispute.status,
        resolution_notes=dispute.resolution_notes,
        created_at=dispute.created_at,
    )


async def list_project_disputes(
    db: AsyncSession,
    project_identifier: str | uuid.UUID,
    user: User,
) -> List[DisputeResponse]:
    """List disputes for a project."""
    project = await resolve_project(db, project_identifier)

    q = (
        select(Dispute)
        .where(Dispute.project_id == project.id)
        .order_by(Dispute.created_at.desc())
    )
    res = await db.execute(q)
    disputes = res.scalars().all()

    return [
        DisputeResponse(
            id=d.id,
            project_id=d.project_id,
            project_code=project.project_code,
            raised_by_id=d.raised_by_id,
            reason=d.reason,
            status=d.status,
            resolution_notes=d.resolution_notes,
            created_at=d.created_at,
        )
        for d in disputes
    ]


async def resolve_dispute(
    db: AsyncSession,
    dispute_id: uuid.UUID,
    user: User,
    payload: ResolveDisputeRequest,
) -> DisputeResponse:
    """
    Admin resolves an audit dispute.
    Can uphold the original decision, schedule re-audit, or issue revised decision
    without overwriting past records.
    """
    if user.role not in (UserRole.AUDITOR, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only platform administrators or auditors can resolve disputes.",
        )

    dispute = await db.get(Dispute, dispute_id)
    if not dispute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dispute {dispute_id} not found.",
        )

    dispute.status = DisputeStatus.RESOLVED
    dispute.resolution_notes = payload.resolution_notes

    # If revising decision, record new decision linked via superseded_by_id
    if payload.action == "REVISE_DECISION" and payload.revised_decision:
        aud_q = (
            select(Audit)
            .options(selectinload(Audit.decisions))
            .where(Audit.project_id == dispute.project_id)
            .order_by(Audit.created_at.desc())
        )
        aud_res = await db.execute(aud_q)
        audit = aud_res.scalars().first()
        if audit:
            req = AuditDecisionCreateRequest(
                decision=payload.revised_decision,
                findings=payload.revised_findings or f"Revised following dispute resolution: {payload.resolution_notes}",
                notes=f"Dispute {dispute.id} resolved by {user.full_name}",
            )
            await record_audit_decision(db, audit.id, user, req)

    await _log_audit_activity(
        db=db,
        user=user,
        action="DISPUTE_RESOLVED",
        resource_type="dispute",
        resource_id=str(dispute.id),
        detail={
            "action": payload.action,
            "resolution_notes": payload.resolution_notes,
            "project_id": str(dispute.project_id),
        },
    )

    await db.commit()
    await db.refresh(dispute)

    return DisputeResponse(
        id=dispute.id,
        project_id=dispute.project_id,
        raised_by_id=dispute.raised_by_id,
        reason=dispute.reason,
        status=dispute.status,
        resolution_notes=dispute.resolution_notes,
        created_at=dispute.created_at,
    )
