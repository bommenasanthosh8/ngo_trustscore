"""
Projects router — /projects and /api/v1/projects endpoints.
Handles project creation, paginated filtered browsing, detail lookup,
geospatial search, and state transitions with ownership authorization.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.core.responses import ok
from app.dependencies import CurrentUserDep, DbDep, OptionalUserDep, require_roles
from app.models.enums import EvidenceType, FinancialDocumentType, ProjectStatus, ProjectType
from app.projects import service
from app.projects.schemas import (
    CreateProjectRequest,
    LocationSearchResult,
    ProjectDetail,
    ProjectSummary,
    UpdateProjectRequest,
)
from app.schemas.audit import CreateDisputeRequest
from app.schemas.evidence import EvidenceUploadMetadata
from app.schemas.financial_evidence import FinancialEvidenceUploadMetadata
from app.services import evidence_service, financial_evidence_service

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post(
    "",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("NGO", "ADMIN"))],
)
@router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("NGO", "ADMIN"))],
    include_in_schema=False,
)
async def create_project(
    body: CreateProjectRequest,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Create a new project with PostGIS geofenced site.
    Generates a unique human-readable Project ID (e.g. NGO-WELL-2026-0001).
    Restricted to NGO representatives and platform administrators.
    """
    project = await service.create_project(db, current_user, body)
    return ok(
        ProjectDetail.model_validate(project),
        message="Project registered successfully in CREATED state.",
    )


@router.get("/my", response_model=dict)
@router.get("/my/", response_model=dict, include_in_schema=False)
async def list_my_projects(
    current_user: CurrentUserDep,
    db: DbDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List projects belonging to the authenticated NGO."""
    if not current_user.ngo_id:
        return ok([])
    projects, total = await service.list_projects(
        db,
        skip=skip,
        limit=limit,
        ngo_id=current_user.ngo_id,
    )
    return ok([ProjectDetail.model_validate(p) for p in projects])


@router.get("", response_model=dict)
@router.get("/", response_model=dict, include_in_schema=False)
async def list_projects(
    db: DbDep,
    current_user: OptionalUserDep = None,
    category: Optional[ProjectType] = Query(None, description="Filter by sector/category"),
    status: Optional[ProjectStatus] = Query(None, description="Filter by lifecycle status"),
    search: Optional[str] = Query(None, description="Search title, description, or location"),
    ngo_id: Optional[uuid.UUID] = Query(None, description="Filter by owning NGO"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    List projects with pagination and comprehensive filtering.
    Publicly accessible to Donors, NGOs, Auditors, and Admins.
    Private unverified projects are filtered out unless requested by owning NGO or Admin.
    """
    from app.models.enums import UserRole

    is_privileged = bool(current_user and current_user.role in (UserRole.ADMIN, UserRole.AUDITOR))
    is_owner = bool(current_user and current_user.role == UserRole.NGO and current_user.ngo_id and current_user.ngo_id == ngo_id)
    public_only = not (is_privileged or is_owner)

    projects, total = await service.list_projects(
        db,
        skip=skip,
        limit=limit,
        category=category,
        status=status,
        search=search,
        ngo_id=ngo_id,
        public_only=public_only,
    )
    return ok(
        [ProjectDetail.model_validate(p) for p in projects],
        message=f"Retrieved {len(projects)} projects (total: {total}).",
    )


@router.get("/locations/search", response_model=dict)
async def search_locations(
    q: str = Query("", description="Location query term"),
):
    """
    Location lookup helper for the frontend map picker.
    Provides verified site geocoding coordinates across India.
    """
    results = service.search_locations(q)
    return ok([r.model_dump() for r in results])


@router.get("/{id}", response_model=dict)
async def get_project(
    id: str,
    db: DbDep,
    current_user: OptionalUserDep = None,
):
    """
    Retrieve single project details.
    Supports lookup by either internal UUID or human-readable Project ID (e.g. NGO-WELL-2026-0001).
    Enforces data isolation: private projects require owning NGO, Auditor, or Admin privileges.
    Sensitive coordinates are fuzzed for non-privileged visitors.
    """
    from app.core.exceptions import ForbiddenException, NotFoundException
    from app.models.enums import UserRole

    project = await service.get_project_by_id(db, id)

    # If project is private, restrict to owning NGO, Auditor, Admin
    if not project.is_publicly_visible:
        if current_user is None:
            raise NotFoundException("Project")
        if current_user.role not in (UserRole.ADMIN, UserRole.AUDITOR):
            if not (current_user.role == UserRole.NGO and current_user.ngo_id and project.ngo_id == current_user.ngo_id):
                raise ForbiddenException("You do not have permission to access this private project.")

    detail = ProjectDetail.model_validate(project)
    is_sensitive = getattr(project, "is_sensitive", False) or project.project_type in (ProjectType.HEALTHCARE, ProjectType.RELIEF_DISTRIBUTION)
    if is_sensitive:
        is_privileged = current_user and (
            current_user.role in (UserRole.ADMIN, UserRole.AUDITOR) or
            (current_user.role == UserRole.NGO and current_user.ngo_id and current_user.ngo_id == project.ngo_id)
        )
        if not is_privileged:
            # Mask precise coordinates with approximate fuzzing
            detail.latitude = detail.approximate_latitude
            detail.longitude = detail.approximate_longitude

    return ok(detail)


@router.patch("/{id}", response_model=dict)
async def update_project(
    id: str,
    body: UpdateProjectRequest,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Update project details or advance status along the state machine.
    Enforces NGO ownership authorization: only owning NGO representatives or Admins may update.
    Arbitrary status jumps are rejected by the backend state transition rules.
    """
    project = await service.update_project(db, current_user, id, body)
    return ok(
        ProjectDetail.model_validate(project),
        message="Project updated successfully.",
    )


# ── Evidence Collection & Milestones ─────────────────────────────────────────
@router.post(
    "/{id}/evidence",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("NGO", "ADMIN"))],
)
async def upload_project_evidence(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
    file: UploadFile = File(...),
    title: str = Form(...),
    evidence_type: EvidenceType = Form(...),
    description: Optional[str] = Form(None),
    captured_at: Optional[datetime] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    gps_accuracy: Optional[float] = Form(None),
    supersedes_id: Optional[uuid.UUID] = Form(None),
    metadata_summary: Optional[str] = Form(None),
):
    """
    Upload and register an immutable evidence item bound to exactly one Project.
    Generates SHA-256 hash, validates file types, captures GPS coordinates (or marks
    LOCATION_UNAVAILABLE), logs audit activity, and respects correction superseding.
    """
    parsed_meta = {}
    if metadata_summary:
        try:
            parsed_meta = json.loads(metadata_summary)
        except Exception:
            parsed_meta = {"notes": metadata_summary}

    meta = EvidenceUploadMetadata(
        title=title,
        evidence_type=evidence_type,
        description=description,
        captured_at=captured_at,
        latitude=latitude,
        longitude=longitude,
        gps_accuracy=gps_accuracy,
        supersedes_id=supersedes_id,
        metadata_summary=parsed_meta,
    )
    evidence = await evidence_service.upload_evidence(db, current_user, id, file, meta)
    serialized = evidence_service._serialize_evidence(evidence)
    return ok(serialized.model_dump(), message="Evidence uploaded and registered successfully.")


@router.get("/{id}/evidence", response_model=dict)
async def list_project_evidence(
    id: str,
    db: DbDep,
    current_user: OptionalUserDep = None,
    evidence_type: Optional[EvidenceType] = Query(None, description="Filter by evidence type (BEFORE, PROGRESS, COMPLETION, etc.)"),
):
    """
    List all evidence records for a project, optionally filtered by evidence_type.
    Accessible to donors/public for visible non-disputed projects.
    """
    result = await evidence_service.get_project_evidence_list(db, current_user, id, evidence_type)
    return ok(result.model_dump())


@router.get("/{id}/evidence/timeline", response_model=dict)
async def get_project_evidence_timeline(
    id: str,
    db: DbDep,
    current_user: OptionalUserDep = None,
):
    """
    Retrieve the chronological evidence timeline for a project, including milestone
    summaries (BEFORE, PROGRESS, COMPLETION, EVENT, FINANCIAL, OTHER) and revision chains.
    Accessible to donors/public for visible non-disputed projects.
    """
    timeline = await evidence_service.get_project_evidence_timeline(db, current_user, id)
    return ok(timeline.model_dump())



@router.get("/{id}/evidence/{evidence_id}/file")
async def download_project_evidence_file(
    id: str,
    evidence_id: uuid.UUID,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Securely download or stream an evidence file with ownership verification.
    """
    file_path, mime_type, original_filename = await evidence_service.get_evidence_file(db, current_user, evidence_id)
    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=original_filename,
    )


# ── Financial Evidence & Expenditure Consistency ─────────────────────────────
@router.post(
    "/{id}/financial-evidence",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("NGO", "ADMIN"))],
)
async def upload_financial_evidence(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
    file: UploadFile = File(...),
    claimed_amount: float = Form(...),
    document_type: FinancialDocumentType = Form(FinancialDocumentType.INVOICE),
    currency: str = Form("INR"),
    vendor_name: Optional[str] = Form(None),
    invoice_number: Optional[str] = Form(None),
    document_date: Optional[datetime] = Form(None),
    description: Optional[str] = Form(None),
):
    """
    Upload and process a financial evidence document (invoice, bill, receipt, statement).
    Performs deterministic OCR extraction, duplicate detection, and amount verification.
    """
    metadata = FinancialEvidenceUploadMetadata(
        claimed_amount=claimed_amount,
        document_type=document_type,
        currency=currency,
        vendor_name=vendor_name,
        invoice_number=invoice_number,
        document_date=document_date,
        description=description,
    )
    fin_evidence = await financial_evidence_service.upload_financial_evidence(
        db, current_user, id, file, metadata
    )
    serialized = financial_evidence_service._serialize_financial_evidence(fin_evidence)
    return ok(
        serialized.model_dump(),
        message="Financial evidence uploaded and processed successfully.",
    )


@router.get("/{id}/financial-evidence", response_model=dict)
async def get_project_financial_evidence(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Retrieve all financial evidence documents for a project alongside the comprehensive
    financial consistency report comparing target budget, claimed expenditure, and supported documentation.
    """
    res = await financial_evidence_service.get_project_financial_evidence(db, current_user, id)
    return ok(res.model_dump())


@router.get("/{id}/financial-evidence/consistency", response_model=dict)
async def get_project_financial_consistency(
    id: str,
    db: DbDep,
    current_user: OptionalUserDep = None,
):
    """
    Evaluate and retrieve the financial consistency status (CONSISTENT, MINOR_DISCREPANCY,
    MAJOR_DISCREPANCY, INSUFFICIENT_EVIDENCE) and expenditure variance breakdown.
    """
    report = await financial_evidence_service.get_financial_consistency_report(db, current_user, id)
    return ok(report.model_dump())


@router.post("/{id}/verify", response_model=dict)
async def trigger_project_verification(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Trigger the complete 10-point Evidence Verification Engine for this project.
    Restricted to project owning NGO, platform Auditors, and Admins.
    """
    from app.core.exceptions import ForbiddenException
    from app.models.enums import UserRole
    from app.verification.engine import get_verification_engine

    project = await service.get_project_by_id(db, id)
    if current_user.role == UserRole.DONOR:
        raise ForbiddenException("Donors cannot trigger project verification.")
    if current_user.role == UserRole.NGO and project.ngo_id != current_user.ngo_id:
        raise ForbiddenException("You do not have permission to trigger verification for this project.")

    engine = get_verification_engine()
    report = await engine.verify_project(db, project)
    return ok(report.model_dump(mode="json"), message="Verification completed.")


@router.get("/{id}/verification", response_model=dict)
async def get_project_verification_report(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Retrieve current verification evaluation and quality scorecard for this project.
    Private projects are restricted to owning NGO, Auditors, and Admins.
    """
    from app.core.exceptions import ForbiddenException
    from app.models.enums import UserRole
    from app.verification.engine import get_verification_engine

    project = await service.get_project_by_id(db, id)
    if not project.is_publicly_visible:
        if current_user.role == UserRole.DONOR:
            raise ForbiddenException("This project verification is not accessible.")
        if current_user.role == UserRole.NGO and project.ngo_id != current_user.ngo_id:
            raise ForbiddenException("You do not have permission to view verification for this project.")

    engine = get_verification_engine()
    report = await engine.verify_project(db, project)
    return ok(report.model_dump(mode="json"))


@router.get("/{id}/risk", response_model=dict)
async def get_project_risk(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Retrieve or compute comprehensive multi-factor risk assessment for a project.
    Evaluates 10 risk signals, clamping score 0–100, risk levels LOW/MEDIUM/HIGH,
    narrative explanations, and audit triggers.
    Restricted to project owning NGO, platform Auditors, and Admins.
    """
    from app.core.exceptions import ForbiddenException
    from app.models.enums import UserRole
    from app.risk.engine import get_risk_engine

    project = await service.get_project_by_id(db, id)
    if current_user.role == UserRole.DONOR:
        raise ForbiddenException("Donors are not authorized to view internal risk signals.")
    if current_user.role == UserRole.NGO and project.ngo_id != current_user.ngo_id:
        raise ForbiddenException("You do not have permission to view risk analysis for this project.")

    engine = get_risk_engine()
    report = await engine.evaluate_project_risk(db, project)
    return ok(report.model_dump(mode="json"))


@router.post("/{id}/dispute", response_model=dict, status_code=status.HTTP_201_CREATED)
async def raise_project_dispute(
    id: str,
    payload: CreateDisputeRequest,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    NGO requests review of an audit decision for their project.
    Moves project and audit status into DISPUTED and creates an immutable ActivityLog.
    """
    from app.core.exceptions import ForbiddenException
    from app.models.enums import UserRole
    from app.audit.service import create_project_dispute

    project = await service.get_project_by_id(db, id)
    if current_user.role == UserRole.DONOR:
        raise ForbiddenException("Donors cannot lodge project audit disputes.")
    if current_user.role == UserRole.NGO and project.ngo_id != current_user.ngo_id:
        raise ForbiddenException("You do not have permission to dispute audits for this project.")

    dispute = await create_project_dispute(db, id, current_user, payload)
    return ok(
        dispute.model_dump(mode="json"),
        message="Dispute lodged successfully. Project status updated to DISPUTED.",
    )


@router.get("/{id}/disputes", response_model=dict)
async def list_project_disputes_endpoint(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """List historical and active disputes for this project. Restricted to owning NGO, Auditors, and Admins."""
    from app.core.exceptions import ForbiddenException
    from app.models.enums import UserRole
    from app.audit.service import list_project_disputes

    project = await service.get_project_by_id(db, id)
    if current_user.role == UserRole.DONOR:
        raise ForbiddenException("Donors are not authorized to view internal dispute records.")
    if current_user.role == UserRole.NGO and project.ngo_id != current_user.ngo_id:
        raise ForbiddenException("You do not have permission to view disputes for this project.")

    disputes = await list_project_disputes(db, id, current_user)
    return ok([d.model_dump(mode="json") for d in disputes])


@router.get("/{id}/score", response_model=dict)
async def get_project_score(
    id: str,
    db: DbDep,
    current_user: OptionalUserDep = None,
):
    """
    Get the authoritative 100-point project evidence score.
    Returns 6-factor breakdown (Location, Timeline, Media, Financial, Identity, Audit),
    status (STRONG_EVIDENCE, GOOD_EVIDENCE, LIMITED_EVIDENCE, WEAK_EVIDENCE),
    and active dispute status. Publicly accessible to donors for visible projects.
    """
    from app.core.exceptions import NotFoundException
    from app.models.enums import UserRole
    from app.scores.service import get_or_calculate_project_score

    project = await service.get_project_by_id(db, id)
    if not project.is_publicly_visible:
        is_privileged = current_user and (
            current_user.role in (UserRole.ADMIN, UserRole.AUDITOR)
            or (current_user.role == UserRole.NGO and project.ngo_id == current_user.ngo_id)
        )
        if not is_privileged:
            raise NotFoundException(f"Project with ID '{id}' was not found.")

    score_resp = await get_or_calculate_project_score(db, id)
    return ok(score_resp.model_dump(mode="json"))


@router.get("/{id}/audits", response_model=dict)
async def get_project_audits(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Retrieve independent audit records and decisions for this project.
    Accessible to project owning NGO, platform Auditors, and Admins.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.audit import Audit
    from app.models.enums import UserRole
    from app.core.exceptions import ForbiddenException

    project = await service.get_project_by_id(db, id)
    if current_user.role == UserRole.DONOR:
        raise ForbiddenException("Donors are not authorized to view internal audit records.")
    if current_user.role == UserRole.NGO and project.ngo_id != current_user.ngo_id:
        raise ForbiddenException("You do not have permission to view audits for this project.")

    query = (
        select(Audit)
        .where(Audit.project_id == project.id)
        .options(selectinload(Audit.decisions))
        .order_by(Audit.created_at.desc())
    )
    result = await db.execute(query)
    audits = list(result.scalars().all())
    data = [
        {
            "id": str(a.id),
            "project_id": str(a.project_id),
            "selection_reason": a.selection_reason.value if hasattr(a.selection_reason, "value") else str(a.selection_reason),
            "status": a.status.value if hasattr(a.status, "value") else str(a.status),
            "scope": a.scope,
            "findings": a.findings,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "decisions": [
                {
                    "id": str(d.id),
                    "decision": d.decision.value if hasattr(d.decision, "value") else str(d.decision),
                    "notes": d.notes,
                    "findings": d.findings,
                    "decided_at": d.decided_at.isoformat() if d.decided_at else None,
                }
                for d in a.decisions
            ],
        }
        for a in audits
    ]
    return ok(data)
