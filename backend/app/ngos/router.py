"""
NGO router — /ngos and /api/v1/ngos endpoints.
Handles NGO onboarding, profile retrieval, and profile updates.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Query, status

from app.core.responses import ok
from app.dependencies import CurrentUserDep, DbDep
from app.models.enums import NGOVerificationStatus
from app.schemas.ngo import NGOCreateRequest, NGOResponse, NGOUpdateRequest
from app.services import ngo_service

router = APIRouter(prefix="/ngos", tags=["NGOs"])


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_ngo(
    body: NGOCreateRequest,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Onboard a new NGO.
    Verification status is initialized to PENDING.
    Only users with role NGO or ADMIN can create an NGO.
    """
    ngo = await ngo_service.create_ngo(db, current_user, body)
    return ok(
        NGOResponse.model_validate(ngo),
        message="NGO onboarding submitted successfully. Status is PENDING admin review.",
    )


@router.get("", response_model=dict)
async def list_ngos(
    db: DbDep,
    status_filter: Optional[NGOVerificationStatus] = Query(None, alias="status"),
    search: Optional[str] = Query(None, description="Search by NGO name, description, or registration number"),
    category: Optional[str] = Query(None, description="Filter by project category"),
    location: Optional[str] = Query(None, description="Filter by location/address"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """
    List NGOs with optional verification status, search, category, and location filters.
    Returns enriched summaries including project counts, categories, and Transparency Scores.
    """
    summaries = await ngo_service.list_all_ngos(
        db,
        status=status_filter,
        search=search,
        category=category,
        location=location,
        skip=skip,
        limit=limit,
    )
    return ok([s.model_dump(mode="json") for s in summaries])



@router.get("/{id}", response_model=dict)
async def get_ngo(id: uuid.UUID, db: DbDep):
    """Retrieve an NGO profile by its unique identifier."""
    ngo = await ngo_service.get_ngo_by_id(db, id)
    return ok(NGOResponse.model_validate(ngo))


@router.patch("/{id}", response_model=dict)
async def update_ngo(
    id: uuid.UUID,
    body: NGOUpdateRequest,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Update NGO profile details.
    Only authorized representatives of this NGO or platform ADMINs may update.
    Verification status cannot be changed via this endpoint.
    """
    ngo = await ngo_service.update_ngo(db, current_user, id, body)
    return ok(
        NGOResponse.model_validate(ngo),
        message="NGO profile updated successfully.",
    )


@router.get("/{id}/score", response_model=dict)
async def get_ngo_score(
    id: uuid.UUID,
    db: DbDep,
):
    """
    Get the authoritative NGO Transparency Score.
    Aggregates historical project verification performance, evidence scores,
    financial values, audit history, and disputes into an explainable indicator.
    """
    from app.scores.service import get_or_calculate_ngo_score
    score_resp = await get_or_calculate_ngo_score(db, id)
    return ok(score_resp.model_dump(mode="json"))


@router.get("/{id}/score/history", response_model=dict)
async def get_ngo_score_history(
    id: uuid.UUID,
    db: DbDep,
):
    """
    List historical ScoreSnapshots for this NGO.
    """
    from app.scores.service import list_ngo_score_snapshots
    snapshots = await list_ngo_score_snapshots(db, id)
    data = [
        {
            "id": str(s.id),
            "ngo_id": str(s.ngo_id),
            "composite_score": float(s.composite_score),
            "breakdown": s.breakdown,
            "calculated_at": s.calculated_at.isoformat(),
        }
        for s in snapshots
    ]
    return ok(data)

