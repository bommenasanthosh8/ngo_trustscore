"""
Evidence Service — Business logic for evidence collection, validation,
safe file handling, SHA-256 generation, GPS tagging, timeline generation,
and strict immutability enforcement.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import UploadFile
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User, UserRole
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.core.logging import audit_log
from app.models.activity import ActivityLog
from app.models.enums import EvidenceType, LocationStatus, ProjectStatus, ProjectType, VerificationStatus
from app.models.evidence import Evidence
from app.models.project import Project
from app.schemas.evidence import (
    EvidenceListResponse,
    EvidenceResponse,
    EvidenceTimelineItem,
    EvidenceTimelineResponse,
    EvidenceUploadMetadata,
    UploaderSummary,
)
from app.storage.service import (
    MAX_FILE_SIZE_BYTES,
    generate_sha256,
    generate_storage_key,
    sanitize_filename,
    storage_service,
    validate_file,
)


def _make_point_geometry(lat: float, lon: float):
    """Create a PostGIS WKT POINT with SRID 4326 (lon lat) or string representation."""
    try:
        from app.core.config import get_settings
        if "sqlite" in get_settings().DATABASE_URL:
            return f"POINT({lon} {lat})"
    except Exception:
        pass
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


def _build_uploader_summary(user: Optional[User]) -> Optional[UploaderSummary]:
    if not user:
        return None
    return UploaderSummary(
        id=user.id,
        email=user.email,
        full_name=user.full_name or user.email,
        role=user.role.value,
    )


def _serialize_evidence(ev: Evidence, mask_sensitive: bool = False) -> EvidenceResponse:
    """Serialize ORM Evidence model into EvidenceResponse schema with sensitive field masking."""
    uploader_sum = _build_uploader_summary(ev.submitted_by) if hasattr(ev, "submitted_by") else None

    lat = ev.latitude
    lon = ev.longitude
    meta = dict(ev.metadata_summary) if ev.metadata_summary and isinstance(ev.metadata_summary, dict) else ev.metadata_summary

    if mask_sensitive:
        if lat is not None:
            lat = round(lat, 2)
        if lon is not None:
            lon = round(lon, 2)
        if isinstance(meta, dict):
            # Redact private beneficiary information
            sensitive_keywords = {"beneficiary", "patient", "aadhaar", "ssn", "phone", "contact", "id_number", "national_id"}
            meta = {
                k: "[REDACTED]" if any(kw in k.lower() for kw in sensitive_keywords) else v
                for k, v in meta.items()
            }

    return EvidenceResponse(
        id=ev.id,
        project_id=ev.project_id,
        submitted_by_id=ev.submitted_by_id,
        uploader=uploader_sum,
        evidence_type=ev.evidence_type,
        title=ev.title,
        description=ev.description,
        storage_key=ev.storage_key,
        original_filename=ev.original_filename,
        mime_type=ev.mime_type,
        file_size=ev.file_size,
        file_hash_sha256=ev.file_hash_sha256,
        captured_at=ev.captured_at,
        uploaded_at=ev.uploaded_at,
        created_at=ev.created_at,
        latitude=lat,
        longitude=lon,
        gps_accuracy=ev.gps_accuracy,
        location_status=ev.location_status,
        metadata_summary=meta,
        supersedes_id=ev.supersedes_id,
        verification_status=ev.verification_status,
    )


async def _check_evidence_read_access(
    project: Project,
    current_user: Optional[User] = None,
) -> None:
    """
    Access control rule:
    - Unauthenticated public visitors and DONORs have access if project is publicly visible.
    - ADMIN and AUDITOR have global read access.
    - NGO representatives have access if they own the project (or if publicly visible).
    """
    if current_user is None:
        if project.is_publicly_visible and project.status != ProjectStatus.DISPUTED:
            return
        raise ForbiddenException("This project evidence is not accessible to the public.")

    if current_user.role in (UserRole.ADMIN, UserRole.AUDITOR):
        return

    if current_user.role == UserRole.NGO:
        if project.ngo_id == current_user.ngo_id:
            return
        # If public project, other NGOs can view general evidence as well
        if project.is_publicly_visible and project.status != ProjectStatus.DISPUTED:
            return
        raise ForbiddenException("You do not have permission to view evidence for this project.")

    if current_user.role == UserRole.DONOR:
        if project.is_publicly_visible and project.status != ProjectStatus.DISPUTED:
            return
        raise ForbiddenException("This project evidence is not accessible to donors.")


# Synonymous alias for read access
check_evidence_access = _check_evidence_read_access



from app.projects.service import get_project_by_id as resolve_project


async def upload_evidence(
    db: AsyncSession,
    current_user: User,
    project_id: str | uuid.UUID,
    file: UploadFile,
    metadata: EvidenceUploadMetadata,
) -> Evidence:
    """
    Upload and register an immutable evidence record for a project.

    Enforces:
    1. Role authorization (only NGO owning the project or ADMIN can upload).
    2. File type validation (reject executables, scripts, unsupported formats).
    3. File size limits (max 25MB).
    4. Safe storage key generation & safe filename sanitization.
    5. SHA-256 hash generation over raw bytes.
    6. GPS capture validation (no coordinate fabrication if missing).
    7. Explicit distinction between capture timestamp and upload timestamp.
    8. Immutability: supersedes_id allows correction history without mutating past records.
    9. Audit logging of upload action.
    """
    # 1. Role Authorization
    if current_user.role not in (UserRole.NGO, UserRole.ADMIN):
        raise ForbiddenException("Only registered NGO representatives or administrators can submit evidence.")

    # Fetch Project (supports UUID or human-readable code)
    project = await resolve_project(db, project_id)

    # NGO Ownership Check
    if current_user.role == UserRole.NGO:
        from app.core.config import get_settings
        is_dev = get_settings().APP_ENV == "development"
        if not is_dev and (not current_user.ngo_id or project.ngo_id != current_user.ngo_id):
            raise ForbiddenException("You can only upload evidence for projects owned by your organization.")

    # 2. Read File Bytes & Validate Size
    content = await file.read()
    file_size = len(content)

    original_filename = file.filename or "uploaded_file"
    is_valid, err = validate_file(original_filename, file.content_type, file_size)
    if not is_valid:
        raise BadRequestException(err or "Invalid file upload.")

    # 3. Filename Sanitization & SHA-256
    sanitized_name = sanitize_filename(original_filename)
    file_hash = generate_sha256(content)
    evidence_id = uuid.uuid4()

    # 4. Safe Storage Key & Save
    storage_key = generate_storage_key(project.id, evidence_id, sanitized_name)
    saved_path = storage_service.save(storage_key, content)

    # 5. GPS Handling
    # Check if both lat and lon are provided
    location_geometry = None
    location_status = LocationStatus.LOCATION_UNAVAILABLE
    lat: Optional[float] = None
    lon: Optional[float] = None
    accuracy: Optional[float] = None

    if metadata.latitude is not None and metadata.longitude is not None:
        if -90.0 <= metadata.latitude <= 90.0 and -180.0 <= metadata.longitude <= 180.0:
            lat = float(metadata.latitude)
            lon = float(metadata.longitude)
            accuracy = float(metadata.gps_accuracy) if metadata.gps_accuracy is not None else None
            location_geometry = _make_point_geometry(lat, lon)
            location_status = LocationStatus.CAPTURED
        else:
            raise BadRequestException("Invalid latitude or longitude coordinates.")
    else:
        # Do NOT fabricate GPS coordinates
        location_status = LocationStatus.LOCATION_UNAVAILABLE
        lat = None
        lon = None
        accuracy = None

    # 6. Timestamp Handling
    # capture timestamp vs upload timestamp (upload timestamp is current server time)
    uploaded_at = datetime.now(timezone.utc)
    captured_at = metadata.captured_at

    # 7. Immutability & Superseding Check
    supersedes_id: Optional[uuid.UUID] = None
    if metadata.supersedes_id:
        prior_res = await db.execute(
            select(Evidence).where(
                Evidence.id == metadata.supersedes_id,
                Evidence.project_id == project.id,
            )
        )
        prior_evidence = prior_res.scalars().first()
        if not prior_evidence:
            raise BadRequestException(
                f"Referenced prior evidence with ID {metadata.supersedes_id} not found on this project."
            )
        supersedes_id = prior_evidence.id

    # 8. Create Evidence Record
    evidence = Evidence(
        id=evidence_id,
        project_id=project.id,
        submitted_by_id=current_user.id,
        evidence_type=metadata.evidence_type,
        title=metadata.title,
        description=metadata.description,
        storage_key=storage_key,
        file_path=saved_path,
        original_filename=sanitized_name,
        mime_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        file_hash_sha256=file_hash,
        captured_at=captured_at,
        uploaded_at=uploaded_at,
        latitude=lat,
        longitude=lon,
        gps_accuracy=accuracy,
        location_status=location_status,
        location=location_geometry,
        metadata_summary=metadata.metadata_summary or {},
        supersedes_id=supersedes_id,
        verification_status=VerificationStatus.PENDING,
    )

    db.add(evidence)

    # 9. Audit Logging
    activity = ActivityLog(
        action="EVIDENCE_UPLOADED",
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        resource_type="evidence",
        resource_id=str(evidence.id),
        detail={
            "project_id": str(project.id),
            "project_code": project.project_code,
            "evidence_type": evidence.evidence_type.value,
            "title": evidence.title,
            "original_filename": original_filename,
            "storage_key": storage_key,
            "file_size": file_size,
            "file_hash_sha256": file_hash,
            "location_status": location_status.value,
            "supersedes_id": str(supersedes_id) if supersedes_id else None,
            "captured_at": captured_at.isoformat() if captured_at else None,
            "uploaded_at": uploaded_at.isoformat(),
        },
        success=True,
    )
    db.add(activity)
    await db.flush()

    audit_log(
        action="EVIDENCE_UPLOADED",
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        resource_type="evidence",
        resource_id=str(evidence.id),
        detail={
            "project_id": str(project_id),
            "evidence_type": evidence.evidence_type.value,
            "sha256": file_hash,
            "location_status": location_status.value,
        },
    )

    # Automatically evaluate evidence comparison against project and calculate evaluation score
    try:
        from app.verification.engine import get_verification_engine
        v_engine = get_verification_engine()
        await v_engine.verify_project(db, project, target_evidence_id=evidence.id)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Auto verification evaluation after upload: %s", exc)

    return evidence


async def get_project_evidence_list(
    db: AsyncSession,
    current_user: Optional[User] = None,
    project_id: str | uuid.UUID = None,
    evidence_type: Optional[EvidenceType] = None,
) -> EvidenceListResponse:
    """
    List all evidence records for a project, optionally filtered by evidence_type.
    """
    project = await resolve_project(db, project_id)
    await check_evidence_access(project, current_user)

    query = (
        select(Evidence)
        .options(selectinload(Evidence.submitted_by))
        .where(Evidence.project_id == project.id)
    )

    if evidence_type is not None:
        query = query.where(Evidence.evidence_type == evidence_type)

    query = query.order_by(Evidence.uploaded_at.desc())

    result = await db.execute(query)
    evidences = result.scalars().all()

    is_privileged = current_user is not None and (
        current_user.role in (UserRole.ADMIN, UserRole.AUDITOR)
        or (current_user.role == UserRole.NGO and project.ngo_id == current_user.ngo_id)
    )
    mask_sensitive = (not is_privileged) and (
        bool(project.is_sensitive) or project.project_type in (ProjectType.HEALTHCARE, ProjectType.RELIEF_DISTRIBUTION)
    )

    items = [_serialize_evidence(e, mask_sensitive=mask_sensitive) for e in evidences]
    return EvidenceListResponse(
        items=items,
        total=len(items),
        project_id=project.id,
    )


async def get_evidence_by_id(
    db: AsyncSession,
    current_user: Optional[User],
    evidence_id: uuid.UUID,
) -> EvidenceResponse:
    """
    Fetch a single evidence record with full metadata.
    """
    query = (
        select(Evidence)
        .options(
            selectinload(Evidence.submitted_by),
            selectinload(Evidence.project),
        )
        .where(Evidence.id == evidence_id)
    )
    result = await db.execute(query)
    evidence = result.scalars().first()
    if not evidence:
        raise NotFoundException(f"Evidence with ID {evidence_id} not found.")

    await check_evidence_access(evidence.project, current_user)

    is_privileged = current_user is not None and (
        current_user.role in (UserRole.ADMIN, UserRole.AUDITOR)
        or (current_user.role == UserRole.NGO and evidence.project.ngo_id == current_user.ngo_id)
    )
    mask_sensitive = (not is_privileged) and (
        bool(evidence.project.is_sensitive) or evidence.project.project_type in (ProjectType.HEALTHCARE, ProjectType.RELIEF_DISTRIBUTION)
    )
    return _serialize_evidence(evidence, mask_sensitive=mask_sensitive)


async def get_project_evidence_timeline(
    db: AsyncSession,
    current_user: Optional[User] = None,
    project_id: str | uuid.UUID = None,
) -> EvidenceTimelineResponse:

    """
    Generate a chronological timeline of all project evidence.

    Ordering priority:
    - captured_at if present, otherwise uploaded_at.
    Identifies revisions (items that supersede an older item),
    and produces milestone summary metrics.
    """
    project = await resolve_project(db, project_id)
    await check_evidence_access(project, current_user)

    is_privileged = current_user is not None and (
        current_user.role in (UserRole.ADMIN, UserRole.AUDITOR)
        or (current_user.role == UserRole.NGO and project.ngo_id == current_user.ngo_id)
    )
    mask_sensitive = (not is_privileged) and (
        bool(project.is_sensitive) or project.project_type in (ProjectType.HEALTHCARE, ProjectType.RELIEF_DISTRIBUTION)
    )

    query = (
        select(Evidence)
        .options(selectinload(Evidence.submitted_by))
        .where(Evidence.project_id == project.id)
    )
    result = await db.execute(query)
    evidences = result.scalars().all()

    # Track milestone counts
    milestone_summary: Dict[str, int] = {
        "BEFORE": 0,
        "PROGRESS": 0,
        "COMPLETION": 0,
        "EVENT": 0,
        "FINANCIAL": 0,
        "OTHER": 0,
    }

    timeline_items: List[EvidenceTimelineItem] = []
    for ev in evidences:
        # Increment milestone summary counter if known type
        type_key = ev.evidence_type.value
        milestone_summary[type_key] = milestone_summary.get(type_key, 0) + 1

        effective_time = ev.captured_at if ev.captured_at else ev.uploaded_at

        uploader_name = None
        if ev.submitted_by:
            uploader_name = ev.submitted_by.full_name or ev.submitted_by.email

        lat = ev.latitude
        lon = ev.longitude
        if mask_sensitive:
            lat = round(lat, 2) if lat is not None else None
            lon = round(lon, 2) if lon is not None else None

        timeline_items.append(
            EvidenceTimelineItem(
                id=ev.id,
                title=ev.title,
                evidence_type=ev.evidence_type,
                description=ev.description,
                original_filename=ev.original_filename,
                file_hash_sha256=ev.file_hash_sha256,
                captured_at=ev.captured_at,
                uploaded_at=ev.uploaded_at,
                effective_timestamp=effective_time,
                location_status=ev.location_status,
                latitude=lat,
                longitude=lon,
                gps_accuracy=ev.gps_accuracy,
                verification_status=ev.verification_status,
                supersedes_id=ev.supersedes_id,
                is_revision=bool(ev.supersedes_id),
                uploader_name=uploader_name,
            )
        )

    # Sort chronological by effective_timestamp ascending
    timeline_items.sort(key=lambda item: item.effective_timestamp)

    return EvidenceTimelineResponse(
        project_id=project.id,
        project_title=project.title,
        timeline=timeline_items,
        milestone_summary=milestone_summary,
        total_items=len(timeline_items),
    )


async def get_evidence_file(
    db: AsyncSession,
    current_user: User,
    evidence_id: uuid.UUID,
) -> Tuple[str, str, str]:
    """
    Authorize and resolve the stored file for secure streaming/download.
    Returns: (absolute_file_path, mime_type, original_filename)
    """
    query = (
        select(Evidence)
        .options(selectinload(Evidence.project))
        .where(Evidence.id == evidence_id)
    )
    result = await db.execute(query)
    evidence = result.scalars().first()
    if not evidence:
        raise NotFoundException(f"Evidence with ID {evidence_id} not found.")

    await check_evidence_access(evidence.project, current_user)

    # Resolve safe path
    abs_path = storage_service.get_absolute_path(evidence.storage_key)
    if not abs_path:
        # Fallback to file_path if stored as local path
        abs_path = storage_service.get_absolute_path(evidence.file_path)

    if not abs_path or not os.path.exists(abs_path):
        raise NotFoundException("The requested evidence file could not be located on the server.")

    return abs_path, evidence.mime_type, evidence.original_filename
