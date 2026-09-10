"""
Project service — CRUD operations, human-readable Project ID generation,
PostGIS geospatial mapping, and backend-controlled state machine transitions.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.core.logging import audit_log
from app.models.enums import ProjectStatus, ProjectType
from app.models.ngo import NGO
from app.models.project import Project
from app.projects.schemas import (
    CreateProjectRequest,
    LocationSearchResult,
    UpdateProjectRequest,
)

# ── Category code abbreviations for Project ID generation ─────────────────────
CATEGORY_CODES: dict[ProjectType, str] = {
    ProjectType.WATER_AND_SANITATION: "WELL",
    ProjectType.EDUCATION: "EDU",
    ProjectType.HEALTHCARE: "HLTH",
    ProjectType.INFRASTRUCTURE: "INFR",
    ProjectType.FOOD_DISTRIBUTION: "FOOD",
    ProjectType.ENVIRONMENT: "ENVR",
    ProjectType.RELIEF_DISTRIBUTION: "RELF",
    ProjectType.SANITATION: "WASH",
    ProjectType.OTHER: "GEN",
}

# ── State Machine Transition Rules ───────────────────────────────────────────
VALID_STATE_TRANSITIONS: dict[ProjectStatus, set[ProjectStatus]] = {
    ProjectStatus.CREATED: {ProjectStatus.FUNDING},
    ProjectStatus.FUNDING: {ProjectStatus.EVIDENCE_COLLECTION},
    ProjectStatus.EVIDENCE_COLLECTION: {ProjectStatus.UNDER_VERIFICATION},
    ProjectStatus.UNDER_VERIFICATION: {
        ProjectStatus.VERIFIED,
        ProjectStatus.PARTIALLY_VERIFIED,
        ProjectStatus.PENDING,
        ProjectStatus.DISPUTED,
    },
    ProjectStatus.PENDING: {
        ProjectStatus.EVIDENCE_COLLECTION,  # Resubmit additional evidence
        ProjectStatus.UNDER_VERIFICATION,   # Re-enter verification review
    },
    ProjectStatus.PARTIALLY_VERIFIED: {
        ProjectStatus.EVIDENCE_COLLECTION,
        ProjectStatus.UNDER_VERIFICATION,
    },
    ProjectStatus.DISPUTED: {
        ProjectStatus.UNDER_VERIFICATION,   # Re-opened for administrative audit
    },
    ProjectStatus.VERIFIED: {
        ProjectStatus.DISPUTED,             # A dispute may be raised post-verification
    },
}

# Terminal/Audit statuses restricted to verification engine or platform admin
ADMIN_AUDIT_STATUSES = {
    ProjectStatus.VERIFIED,
    ProjectStatus.PARTIALLY_VERIFIED,
    ProjectStatus.DISPUTED,
}


def _make_geometry(lat: float, lon: float):
    """Convert lat/lon coordinates to a PostGIS WKT POINT with SRID 4326 or text representation."""
    try:
        from app.core.config import get_settings
        if "sqlite" in get_settings().DATABASE_URL:
            return f"POINT({lon} {lat})"
    except Exception:
        pass
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


async def generate_project_code(
    db: AsyncSession,
    category: ProjectType,
    year: int | None = None,
) -> str:
    """
    Generate a unique, human-readable Project ID.
    Example format: NGO-WELL-2026-0001
    """
    if year is None:
        year = datetime.now(timezone.utc).year

    cat_tag = CATEGORY_CODES.get(category, "PRJ")
    prefix = f"NGO-{cat_tag}-{year}-"

    # Query existing project codes matching this prefix
    result = await db.execute(
        select(Project.project_code).where(Project.project_code.like(f"{prefix}%"))
    )
    existing_codes = set(result.scalars().all())

    # Find next sequence number
    sequence = 1
    while f"{prefix}{sequence:04d}" in existing_codes:
        sequence += 1

    return f"{prefix}{sequence:04d}"


def validate_status_transition(
    current_status: ProjectStatus,
    target_status: ProjectStatus,
    user_role: UserRole,
) -> None:
    """
    Ensure the requested status transition adheres strictly to the state machine
    and RBAC role rules. Prevents arbitrary jumps from the client.
    """
    if current_status == target_status:
        return

    allowed_targets = VALID_STATE_TRANSITIONS.get(current_status, set())
    if target_status not in allowed_targets:
        allowed_names = [s.value for s in allowed_targets]
        raise BadRequestException(
            f"Invalid status transition from {current_status.value} to {target_status.value}. "
            f"Allowed target states: {allowed_names}"
        )

    # If transitioning into VERIFIED, PARTIALLY_VERIFIED, or DISPUTED, require ADMIN or AUDITOR
    if target_status in ADMIN_AUDIT_STATUSES and user_role not in (UserRole.ADMIN, UserRole.AUDITOR):
        raise ForbiddenException(
            f"Only platform verification engines, auditors, or administrators can mark a project as {target_status.value}."
        )


async def create_project(
    db: AsyncSession,
    current_user: User,
    payload: CreateProjectRequest,
) -> Project:
    """
    Create a new project.
    Generates a unique human-readable project code, registers the PostGIS geofenced site,
    and sets initial status to CREATED.
    """
    if current_user.role not in (UserRole.NGO, UserRole.ADMIN):
        raise ForbiddenException("Only registered NGO representatives or administrators can create projects.")

    ngo_id = current_user.ngo_id
    if not ngo_id:
        if current_user.role == UserRole.ADMIN:
            first_ngo = (await db.execute(select(NGO))).scalars().first()
            if not first_ngo:
                first_ngo = NGO(
                    name="Apex Development Trust",
                    registration_number=f"REG-{uuid.uuid4().hex[:6].upper()}",
                )
                db.add(first_ngo)
                await db.flush()
            ngo_id = first_ngo.id
        else:
            raise ForbiddenException("Your account is not associated with an NGO. Please onboard your NGO first.")

    loc = payload.location
    project_code = await generate_project_code(db, payload.category)

    project = Project(
        ngo_id=ngo_id,
        created_by_id=current_user.id,
        project_code=project_code,
        title=payload.name,
        description=payload.description,
        project_type=payload.category,
        verification_model=payload.verification_model,
        status=ProjectStatus.CREATED,
        target_amount=payload.target_amount,
        total_budget=payload.target_amount,
        currency="INR",
        expected_beneficiaries=payload.expected_beneficiaries,
        expected_outcome=payload.expected_outcome,
        location_name=loc.location_name if loc else None,
        latitude=loc.latitude if loc else None,
        longitude=loc.longitude if loc else None,
        geofence_radius=loc.geofence_radius if loc else 500.0,
        gps_accuracy=loc.gps_accuracy if loc else None,
        project_location=_make_geometry(loc.latitude, loc.longitude) if loc else None,
        start_date=payload.start_date,
        end_date=payload.expected_completion_date,
        is_publicly_visible=payload.is_publicly_visible,
        is_sensitive=payload.is_sensitive,
    )
    db.add(project)
    await db.flush()

    audit_log(
        action="PROJECT_CREATED",
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        resource_type="Project",
        resource_id=str(project.id),
        detail={
            "project_code": project.project_code,
            "title": project.title,
            "category": project.project_type.value,
            "status": project.status.value,
            "location_name": project.location_name,
            "geofence_radius": project.geofence_radius,
            "target_amount": project.target_amount,
        },
    )
    return project


async def get_project_by_id(
    db: AsyncSession,
    identifier: str | uuid.UUID,
) -> Project:
    """Retrieve a project by either its UUID or human-readable Project ID (e.g. NGO-WELL-2026-0001)."""
    # Check if identifier is a valid UUID
    is_uuid = False
    if isinstance(identifier, uuid.UUID):
        is_uuid = True
    else:
        try:
            parsed_uuid = uuid.UUID(str(identifier))
            identifier = parsed_uuid
            is_uuid = True
        except (ValueError, TypeError):
            is_uuid = False

    if is_uuid:
        query = select(Project).where(Project.id == identifier)
    else:
        query = select(Project).where(Project.project_code == str(identifier))

    result = await db.execute(query)
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundException("Project")
    return project


async def list_projects(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    category: Optional[ProjectType] = None,
    status: Optional[ProjectStatus] = None,
    search: Optional[str] = None,
    ngo_id: Optional[uuid.UUID] = None,
    public_only: bool = False,
) -> Tuple[List[Project], int]:
    """List projects with pagination and comprehensive filtering."""
    query = select(Project)

    if public_only:
        query = query.where(Project.is_publicly_visible == True)
    if category is not None:
        query = query.where(Project.project_type == category)
    if status is not None:
        query = query.where(Project.status == status)
    if ngo_id is not None:
        query = query.where(Project.ngo_id == ngo_id)
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Project.title.ilike(search_pattern),
                Project.description.ilike(search_pattern),
                Project.location_name.ilike(search_pattern),
                Project.project_code.ilike(search_pattern),
            )
        )

    # Count query
    count_query = select(func.count()).select_from(query.subquery())
    total_count = (await db.execute(count_query)).scalar() or 0

    # Paginated results
    result = await db.execute(
        query.order_by(Project.created_at.desc()).offset(skip).limit(limit)
    )
    projects = list(result.scalars().all())
    return projects, total_count


async def update_project(
    db: AsyncSession,
    current_user: User,
    identifier: str | uuid.UUID,
    payload: UpdateProjectRequest,
) -> Project:
    """
    Update project details or execute a valid state transition.
    Enforces NGO ownership authorization.
    """
    project = await get_project_by_id(db, identifier)

    # Authorization: ADMIN or NGO member of owning NGO
    is_admin = current_user.role == UserRole.ADMIN
    is_owner_ngo = current_user.role == UserRole.NGO and current_user.ngo_id == project.ngo_id

    if not (is_admin or is_owner_ngo):
        raise ForbiddenException("You do not have permission to modify this project.")

    # 1. State machine validation if status transition is requested
    if payload.status is not None:
        validate_status_transition(
            current_status=project.status,
            target_status=payload.status,
            user_role=current_user.role,
        )
        project.status = payload.status

    # 2. Update descriptive and numeric fields
    if payload.name is not None:
        project.title = payload.name
    if payload.category is not None:
        project.project_type = payload.category
    if payload.description is not None:
        project.description = payload.description
    if payload.target_amount is not None:
        project.target_amount = payload.target_amount
        project.total_budget = payload.target_amount
    if payload.expected_beneficiaries is not None:
        project.expected_beneficiaries = payload.expected_beneficiaries
    if payload.expected_outcome is not None:
        project.expected_outcome = payload.expected_outcome
    if payload.start_date is not None:
        project.start_date = payload.start_date
    if payload.expected_completion_date is not None:
        project.end_date = payload.expected_completion_date

    # 3. Update location & geofence if provided
    if payload.location is not None:
        loc = payload.location
        project.location_name = loc.location_name
        project.latitude = loc.latitude
        project.longitude = loc.longitude
        project.geofence_radius = loc.geofence_radius
        project.gps_accuracy = loc.gps_accuracy
        project.project_location = _make_geometry(loc.latitude, loc.longitude)

    db.add(project)
    await db.flush()

    audit_log(
        action="PROJECT_UPDATED",
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        resource_type="Project",
        resource_id=str(project.id),
        detail={
            "project_code": project.project_code,
            "status": project.status.value,
            "updated_fields": list(payload.model_dump(exclude_unset=True).keys()),
        },
    )
    return project


# ── Location Geocode / Search Helper ──────────────────────────────────────────
MOCK_LOCATIONS: list[LocationSearchResult] = [
    LocationSearchResult(
        location_name="Rampur Village Community Center",
        display_name="Rampur, Varanasi District, Uttar Pradesh 221001",
        latitude=25.3176,
        longitude=82.9739,
        state="Uttar Pradesh",
    ),
    LocationSearchResult(
        location_name="Shirur Rural Health Center",
        display_name="Shirur Taluka, Pune District, Maharashtra 412210",
        latitude=18.8262,
        longitude=74.3789,
        state="Maharashtra",
    ),
    LocationSearchResult(
        location_name="Bhamragad Tribal School Site",
        display_name="Bhamragad, Gadchiroli District, Maharashtra 442710",
        latitude=19.3850,
        longitude=80.3540,
        state="Maharashtra",
    ),
    LocationSearchResult(
        location_name="Trimbak Water Shed Catchment",
        display_name="Trimbakeshwar, Nashik District, Maharashtra 422212",
        latitude=19.9324,
        longitude=73.5308,
        state="Maharashtra",
    ),
    LocationSearchResult(
        location_name="Chiplun Flood Relief Depot",
        display_name="Chiplun, Ratnagiri District, Maharashtra 415605",
        latitude=17.5323,
        longitude=73.5186,
        state="Maharashtra",
    ),
    LocationSearchResult(
        location_name="Kishangarh Primary School Ground",
        display_name="Kishangarh, Ajmer District, Rajasthan 305801",
        latitude=26.5744,
        longitude=74.8672,
        state="Rajasthan",
    ),
    LocationSearchResult(
        location_name="Sundarbans Mangrove Conservation Zone",
        display_name="Gosaba, South 24 Parganas, West Bengal 743370",
        latitude=22.1648,
        longitude=88.8094,
        state="West Bengal",
    ),
    LocationSearchResult(
        location_name="Dharavi Youth Vocational Center",
        display_name="Dharavi, Mumbai, Maharashtra 400017",
        latitude=19.0433,
        longitude=72.8567,
        state="Maharashtra",
    ),
]


def search_locations(query: str) -> list[LocationSearchResult]:
    """Provide location search results across India to power the map search UI."""
    q = query.strip().lower()
    if not q:
        return MOCK_LOCATIONS[:5]
    matches = [
        loc
        for loc in MOCK_LOCATIONS
        if q in loc.location_name.lower()
        or q in loc.display_name.lower()
        or (loc.state and q in loc.state.lower())
    ]
    return matches if matches else MOCK_LOCATIONS[:3]
