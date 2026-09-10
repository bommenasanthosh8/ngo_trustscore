"""
Evidence router — /evidence and /api/v1/evidence endpoints.
Handles evidence retrieval, secure file downloads with access control,
and RBAC enforcement.
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse

from app.core.responses import ok
from app.dependencies import CurrentUserDep, DbDep, require_roles
from app.services import evidence_service

router = APIRouter(prefix="/evidence", tags=["Evidence"])


@router.get("/health")
async def health():
    return ok(message="Evidence service operational.")


from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.enums import EvidenceType, UserRole
from app.models.evidence import Evidence
from app.models.project import Project
from app.verification.checks.location import calculate_geodetic_distance


@router.get("", response_model=dict)
@router.get("/", response_model=dict, include_in_schema=False)
async def list_all_evidence(
    db: DbDep,
    current_user: CurrentUserDep,
    project_id: Optional[uuid.UUID] = None,
    evidence_type: Optional[EvidenceType] = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    Retrieve all evidence submitted across organization projects.
    Includes project code, project title, NGO details, photo metadata,
    coordinates, distance from project site, captured/uploaded timestamps,
    and current evaluation/verification scores.
    """
    query = (
        select(Evidence)
        .options(
            selectinload(Evidence.project).selectinload(Project.ngo),
            selectinload(Evidence.submitted_by),
        )
        .order_by(Evidence.uploaded_at.desc())
    )

    if project_id:
        query = query.where(Evidence.project_id == project_id)
    if evidence_type:
        query = query.where(Evidence.evidence_type == evidence_type)

    if current_user.role == UserRole.NGO and current_user.ngo_id:
        query = query.join(Project, Evidence.project_id == Project.id).where(Project.ngo_id == current_user.ngo_id)

    res = await db.execute(query.offset(offset).limit(limit))
    evidences = list(res.scalars().all())

    items = []
    for ev in evidences:
        proj = ev.project
        ngo = proj.ngo if proj else None

        distance_m = None
        is_geofence_match = False
        if proj and proj.latitude is not None and proj.longitude is not None and ev.latitude is not None and ev.longitude is not None:
            distance_m = round(calculate_geodetic_distance(proj.latitude, proj.longitude, ev.latitude, ev.longitude), 1)
            is_geofence_match = distance_m <= (proj.geofence_radius or 500.0)

        items.append({
            "id": str(ev.id),
            "project_id": str(ev.project_id),
            "project_code": proj.project_code if proj else None,
            "project_title": proj.title if proj else None,
            "project_location_name": proj.location_name if proj else None,
            "project_latitude": proj.latitude if proj else None,
            "project_longitude": proj.longitude if proj else None,
            "geofence_radius": proj.geofence_radius if proj else 500.0,
            "ngo_name": ngo.name if ngo else None,
            "evidence_type": ev.evidence_type.value if hasattr(ev.evidence_type, "value") else str(ev.evidence_type),
            "title": ev.title,
            "description": ev.description,
            "original_filename": ev.original_filename,
            "mime_type": ev.mime_type,
            "file_size": ev.file_size,
            "file_hash_sha256": ev.file_hash_sha256,
            "file_url": f"/api/v1/projects/{ev.project_id}/evidence/{ev.id}/file",
            "captured_at": ev.captured_at.isoformat() if ev.captured_at else None,
            "uploaded_at": ev.uploaded_at.isoformat() if ev.uploaded_at else None,
            "latitude": ev.latitude,
            "longitude": ev.longitude,
            "gps_accuracy": ev.gps_accuracy,
            "location_status": ev.location_status.value if hasattr(ev.location_status, "value") else str(ev.location_status),
            "distance_from_project_m": distance_m,
            "is_geofence_match": is_geofence_match,
            "verification_status": ev.verification_status.value if hasattr(ev.verification_status, "value") else str(ev.verification_status),
            "project_evidence_score": float(proj.evidence_score) if proj and proj.evidence_score is not None else None,
            "submitted_by": {
                "id": str(ev.submitted_by.id) if ev.submitted_by else None,
                "full_name": ev.submitted_by.full_name if ev.submitted_by else "NGO Field Agent",
                "email": ev.submitted_by.email if ev.submitted_by else None,
                "role": ev.submitted_by.role.value if ev.submitted_by and hasattr(ev.submitted_by.role, "value") else "NGO",
            } if ev.submitted_by else None,
            "metadata_summary": ev.metadata_summary or {},
        })

    return ok(items, message=f"Retrieved {len(items)} evidence dossiers.")


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
async def submit_evidence_stub(
    db: DbDep,
    current_user: CurrentUserDep,
):
    """
    Evidence submission RBAC endpoint (NGO / ADMIN only; DONOR forbidden).
    For full multipart evidence upload with project binding, call POST /projects/{id}/evidence.
    """
    return ok({"message": "Evidence endpoint active. Submit multipart file to /projects/{id}/evidence."})


@router.get("/{id}", response_model=dict)
async def get_evidence(
    id: uuid.UUID,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Retrieve single evidence record with full metadata, location status,
    SHA-256 hash, timestamps, and uploader profile.
    """
    evidence = await evidence_service.get_evidence_by_id(db, current_user, id)
    return ok(evidence.model_dump())


@router.get("/{id}/file")
async def download_evidence_file(
    id: uuid.UUID,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Secure evidence file streaming endpoint with strict access control.
    Prevents unrestricted public access to private evidence files.
    """
    file_path, mime_type, original_filename = await evidence_service.get_evidence_file(db, current_user, id)
    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=original_filename,
    )
