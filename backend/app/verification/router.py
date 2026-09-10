"""
Verification Service Router.

Provides API endpoints for triggering and inspecting multi-point verification reports
at the project and evidence levels.
"""
from __future__ import annotations

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.responses import ok
from app.dependencies import CurrentUserDep, DbDep, require_roles
from app.models.evidence import Evidence
from app.models.project import Project
from app.projects.service import get_project_by_id as resolve_project
from app.verification.engine import get_verification_engine

router = APIRouter(prefix="/verification", tags=["Verification"])


@router.get("/health")
async def health():
    """Returns verification engine status and registered checks."""
    engine = get_verification_engine()
    return ok({
        "status": "HEALTHY",
        "registered_checks": [c.name for c in engine.checks],
        "total_checks": len(engine.checks),
    })


@router.post("/projects/{id}/verify", response_model=dict)
async def verify_project_endpoint(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Execute the 10-point Evidence Verification Engine for a given project.
    Evaluates:
    - LocationCheck (PostGIS registered vs evidence coordinates)
    - TimestampCheck (pre-start, post-completion, compressed timeline)
    - TimelineCheck (lifecycle order per project verification model)
    - DuplicateMediaCheck (internal & cross-project SHA-256 reuse)
    - ImageSimilarityCheck (perceptual similarity adapter across angles)
    - MetadataCheck (EXIF inspection: AVAILABLE, MISSING, SUSPICIOUS)
    - OCRCheck (Project ID, date, amount, signboard consistency)
    - FinancialConsistencyCheck (target vs claimed vs supported expenditure)
    - ProjectIdentityCheck (ownership & project relation integrity)
    - EvidenceCompletenessCheck (category-specific required evidence checklist)
    """
    project = await resolve_project(db, id)
    engine = get_verification_engine()
    report = await engine.verify_project(db, project)

    return ok(
        report.model_dump(mode="json"),
        message="Project evidence verification completed successfully.",
    )


@router.get("/projects/{id}", response_model=dict)
async def get_project_verification(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """Retrieve the latest verification evaluation report for a project."""
    project = await resolve_project(db, id)
    engine = get_verification_engine()
    report = await engine.verify_project(db, project)

    return ok(report.model_dump(mode="json"))


@router.post("/evidence/{id}/verify", response_model=dict)
async def verify_evidence_endpoint(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """Execute verification for a specific target evidence item within its project context."""
    try:
        ev_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid evidence UUID format.",
        )

    ev = await db.get(Evidence, ev_uuid)
    if not ev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found.",
        )

    project = await db.get(Project, ev.project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent project not found.",
        )

    engine = get_verification_engine()
    report = await engine.verify_project(db, project, target_evidence_id=ev.id)

    return ok(
        report.model_dump(mode="json"),
        message="Target evidence verification completed.",
    )
