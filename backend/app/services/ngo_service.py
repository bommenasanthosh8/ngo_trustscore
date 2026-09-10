"""
NGO service — business logic for NGO onboarding, lifecycle management, and admin verification.
"""
from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.core.logging import audit_log
from app.models.enums import NGOVerificationStatus, ProjectStatus
from app.models.ngo import NGO
from app.schemas.ngo import NGOCreateRequest, NGOUpdateRequest


async def create_ngo(db: AsyncSession, current_user: User, payload: NGOCreateRequest) -> NGO:
    """
    Onboard a new NGO.
    Verification status is always initialized to PENDING.
    If the current user is of role NGO, link this NGO to the user account.
    """
    if current_user.role not in (UserRole.NGO, UserRole.ADMIN):
        raise ForbiddenException("Only NGO representatives or platform Administrators can onboard an NGO.")

    if current_user.role == UserRole.NGO and current_user.ngo_id is not None:
        raise ConflictException("Your user account is already associated with an NGO.")

    # Check for duplicate registration number or name
    existing = await db.execute(
        select(NGO).where(
            or_(
                NGO.registration_number == payload.registration_number,
                NGO.name == payload.name,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictException(
            "An NGO with this registration number or organization name already exists."
        )

    ngo = NGO(
        name=payload.name,
        registration_number=payload.registration_number,
        description=payload.description,
        address=payload.address,
        contact_email=str(payload.contact_email) if payload.contact_email else current_user.email,
        contact_phone=payload.contact_phone,
        website=payload.website,
        authorized_representative=payload.authorized_representative or current_user.full_name,
        verification_status=NGOVerificationStatus.PENDING,
        is_verified=False,
    )
    db.add(ngo)
    await db.flush()

    if current_user.role == UserRole.NGO:
        current_user.ngo_id = ngo.id
        db.add(current_user)
        await db.flush()

    audit_log(
        action="NGO_CREATED",
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        resource_type="NGO",
        resource_id=str(ngo.id),
        detail={
            "ngo_name": ngo.name,
            "registration_number": ngo.registration_number,
            "verification_status": ngo.verification_status.value,
            "authorized_representative": ngo.authorized_representative,
        },
    )
    return ngo


async def get_ngo_by_id(db: AsyncSession, ngo_id: uuid.UUID) -> NGO:
    """Retrieve an NGO by ID."""
    result = await db.execute(select(NGO).where(NGO.id == ngo_id))
    ngo = result.scalar_one_or_none()
    if not ngo:
        raise NotFoundException("NGO")
    return ngo


async def update_ngo(
    db: AsyncSession,
    current_user: User,
    ngo_id: uuid.UUID,
    payload: NGOUpdateRequest,
) -> NGO:
    """
    Update NGO profile details.
    Restricted to NGO members who belong to this NGO or platform ADMIN.
    NGO verification status CANNOT be changed via this method.
    """
    ngo = await get_ngo_by_id(db, ngo_id)

    # Permission check: ADMIN or member of this NGO
    is_admin = current_user.role == UserRole.ADMIN
    is_owner_ngo = current_user.role == UserRole.NGO and current_user.ngo_id == ngo.id

    if not (is_admin or is_owner_ngo):
        raise ForbiddenException("You do not have permission to modify this NGO's profile.")

    update_data = payload.model_dump(exclude_unset=True)

    # Validate name uniqueness if changed
    if "name" in update_data and update_data["name"] != ngo.name:
        existing = await db.execute(
            select(NGO).where(NGO.name == update_data["name"], NGO.id != ngo.id)
        )
        if existing.scalar_one_or_none():
            raise ConflictException("An NGO with this name already exists.")

    for field, value in update_data.items():
        if field == "contact_email" and value is not None:
            value = str(value)
        setattr(ngo, field, value)

    # Ensure verification_status is untouched
    db.add(ngo)
    await db.flush()

    audit_log(
        action="NGO_UPDATED",
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        resource_type="NGO",
        resource_id=str(ngo.id),
        detail={"updated_fields": list(update_data.keys())},
    )
    return ngo


async def list_pending_ngos(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
) -> List[NGO]:
    """List all NGOs awaiting administrative verification."""
    result = await db.execute(
        select(NGO)
        .where(NGO.verification_status == NGOVerificationStatus.PENDING)
        .order_by(NGO.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


from app.models.project import Project
from app.models.score import ScoreSnapshot
from app.schemas.ngo import NGOCreateRequest, NGOPublicSummary, NGOUpdateRequest


async def list_all_ngos(
    db: AsyncSession,
    status: Optional[NGOVerificationStatus] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    location: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[NGOPublicSummary]:
    """List NGOs with optional search, category, location, and status filters."""
    query = select(NGO)
    if status is not None:
        query = query.where(NGO.verification_status == status)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                NGO.name.ilike(pattern),
                NGO.description.ilike(pattern),
                NGO.registration_number.ilike(pattern),
            )
        )
    if location:
        loc_pattern = f"%{location.strip()}%"
        query = query.where(NGO.address.ilike(loc_pattern))
    if category:
        # Match NGOs having projects in this category
        query = query.where(
            NGO.id.in_(
                select(Project.ngo_id).where(Project.project_type == category)
            )
        )

    query = query.order_by(NGO.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    ngos = list(result.scalars().all())

    summaries: List[NGOPublicSummary] = []
    for n in ngos:
        # Query project counts & categories
        proj_stmt = select(Project.status, Project.project_type).where(Project.ngo_id == n.id)
        proj_res = await db.execute(proj_stmt)
        proj_rows = proj_res.all()

        p_count = len(proj_rows)
        verified_p_count = sum(1 for r in proj_rows if r[0] == ProjectStatus.VERIFIED)
        cats = sorted(list({r[1].value for r in proj_rows if r[1]}))

        # Query latest score snapshot
        snap_stmt = (
            select(ScoreSnapshot.composite_score)
            .where(
                ScoreSnapshot.ngo_id == n.id,
                ScoreSnapshot.project_id.is_(None),
            )
            .order_by(ScoreSnapshot.calculated_at.desc())
            .limit(1)
        )
        snap_res = await db.execute(snap_stmt)
        latest_score = snap_res.scalar_one_or_none()

        summaries.append(
            NGOPublicSummary(
                id=n.id,
                name=n.name,
                registration_number=n.registration_number,
                description=n.description,
                address=n.address,
                website=n.website,
                verification_status=n.verification_status,
                is_verified=n.is_verified,
                project_count=p_count,
                verified_project_count=verified_p_count,
                transparency_score=float(latest_score) if latest_score is not None else None,
                project_categories=cats,
                created_at=n.created_at,
            )
        )

    return summaries



async def verify_ngo(
    db: AsyncSession,
    admin_user: User,
    ngo_id: uuid.UUID,
) -> NGO:
    """
    Verify an NGO (ADMIN only).
    Sets verification_status to VERIFIED and is_verified to True.
    Note: For prototype purposes, NGO verification is performed by platform ADMIN.
    Does not claim external government integration.
    """
    if admin_user.role != UserRole.ADMIN:
        raise ForbiddenException("Only platform Administrators can verify an NGO.")

    ngo = await get_ngo_by_id(db, ngo_id)

    ngo.verification_status = NGOVerificationStatus.VERIFIED
    ngo.is_verified = True
    ngo.verified_at = datetime.now(timezone.utc)
    ngo.rejection_reason = None

    db.add(ngo)
    await db.flush()

    audit_log(
        action="NGO_VERIFIED",
        actor_id=admin_user.id,
        actor_role=admin_user.role.value,
        resource_type="NGO",
        resource_id=str(ngo.id),
        detail={
            "ngo_name": ngo.name,
            "registration_number": ngo.registration_number,
            "verification_status": ngo.verification_status.value,
            "verified_by_admin": str(admin_user.id),
            "note": "Verified by Admin for prototype platform; no external government integration claimed.",
        },
    )
    return ngo


async def reject_ngo(
    db: AsyncSession,
    admin_user: User,
    ngo_id: uuid.UUID,
    reason: Optional[str] = None,
) -> NGO:
    """
    Reject an NGO (ADMIN only).
    Sets verification_status to REJECTED and is_verified to False.
    """
    if admin_user.role != UserRole.ADMIN:
        raise ForbiddenException("Only platform Administrators can reject an NGO.")

    ngo = await get_ngo_by_id(db, ngo_id)

    ngo.verification_status = NGOVerificationStatus.REJECTED
    ngo.is_verified = False
    ngo.rejection_reason = reason

    db.add(ngo)
    await db.flush()

    audit_log(
        action="NGO_REJECTED",
        actor_id=admin_user.id,
        actor_role=admin_user.role.value,
        resource_type="NGO",
        resource_id=str(ngo.id),
        detail={
            "ngo_name": ngo.name,
            "registration_number": ngo.registration_number,
            "verification_status": ngo.verification_status.value,
            "rejection_reason": reason,
            "rejected_by_admin": str(admin_user.id),
        },
    )
    return ngo
