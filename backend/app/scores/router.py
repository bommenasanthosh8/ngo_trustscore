"""
Scores Router.

Exposes authoritative endpoints for project evidence scores and health.
Scores are strictly calculated server-side; arbitrary score submissions from clients are rejected.
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends

from app.core.responses import ok
from app.dependencies import CurrentUserDep, DbDep
from app.scores import service

router = APIRouter(prefix="/scores", tags=["Scores"])


@router.get("/health")
async def health():
    """Health check for Score Engine."""
    return ok({"status": "HEALTHY", "service": "Project Evidence Score Engine"})


@router.get("/projects/{id}", response_model=dict)
async def get_project_score_endpoint(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Get the authoritative 100-point evidence score for a project.
    Includes 6-factor breakdown, narrative explanations, and dispute status.
    """
    score_resp = await service.get_or_calculate_project_score(db, id)
    return ok(score_resp.model_dump(mode="json"))


@router.post("/projects/{id}/recalculate", response_model=dict)
async def recalculate_project_score_endpoint(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Force authoritative re-computation of a project's evidence score and record snapshot.
    """
    score_resp = await service.get_or_calculate_project_score(db, id, force_recalculate=True)
    return ok(
        score_resp.model_dump(mode="json"),
        message="Project score recalculated and snapshot recorded successfully.",
    )


@router.get("/projects/{id}/snapshots", response_model=dict)
async def list_project_score_snapshots_endpoint(
    id: uuid.UUID,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    List historical score snapshots for this project.
    """
    snapshots = await service.list_score_snapshots(db, id)
    data = [
        {
            "id": str(s.id),
            "project_id": str(s.project_id),
            "composite_score": float(s.composite_score),
            "breakdown": s.breakdown,
            "calculated_at": s.calculated_at.isoformat(),
        }
        for s in snapshots
    ]
    return ok(data)


@router.get("/ngos/{id}", response_model=dict)
async def get_ngo_score_endpoint(
    id: uuid.UUID,
    db: DbDep,
):
    """
    Get the authoritative NGO Transparency Score across its project portfolio.
    """
    score_resp = await service.get_or_calculate_ngo_score(db, id)
    return ok(score_resp.model_dump(mode="json"))


@router.get("/ngos/{id}/snapshots", response_model=dict)
async def list_ngo_score_snapshots_endpoint(
    id: uuid.UUID,
    db: DbDep,
):
    """
    List historical score snapshots for an NGO.
    """
    snapshots = await service.list_ngo_score_snapshots(db, id)
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

