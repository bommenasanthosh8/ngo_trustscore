"""
Risk Assessment Router.

Provides API endpoints for computing, inspecting, and tracking project risk assessments
and audit recommendation triggers.
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.core.responses import ok
from app.dependencies import CurrentUserDep, DbDep
from app.projects.service import get_project_by_id as resolve_project
from app.risk.engine import get_risk_engine

router = APIRouter(prefix="/risk", tags=["Risk Assessment"])


@router.get("/health")
async def risk_health():
    """Returns risk assessment engine status and configured weights."""
    settings = get_settings()
    return ok({
        "status": "HEALTHY",
        "weights": {
            "location_mismatch": settings.RISK_WEIGHT_LOCATION_MISMATCH,
            "financial_discrepancy": settings.RISK_WEIGHT_FINANCIAL_DISCREPANCY,
            "duplicate_media": settings.RISK_WEIGHT_DUPLICATE_MEDIA,
            "suspicious_metadata": settings.RISK_WEIGHT_SUSPICIOUS_METADATA,
            "missing_timeline": settings.RISK_WEIGHT_MISSING_TIMELINE,
            "failed_submissions": settings.RISK_WEIGHT_FAILED_SUBMISSIONS,
            "high_project_value": settings.RISK_WEIGHT_HIGH_PROJECT_VALUE,
            "previous_disputes": settings.RISK_WEIGHT_PREVIOUS_DISPUTES,
            "unusual_patterns": settings.RISK_WEIGHT_UNUSUAL_PATTERNS,
            "incomplete_evidence": settings.RISK_WEIGHT_INCOMPLETE_EVIDENCE,
        },
        "thresholds": {
            "high_project_value_threshold": settings.HIGH_PROJECT_VALUE_THRESHOLD,
            "audit_random_sample_rate": settings.AUDIT_RANDOM_SAMPLE_RATE,
        },
    })


@router.get("/projects/{id}", response_model=dict)
async def get_project_risk_endpoint(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Retrieve or compute comprehensive multi-factor risk assessment for a project.
    Restricted to project owning NGO, platform Auditors, and Admins.
    """
    from app.auth.models import UserRole
    from app.core.exceptions import ForbiddenException

    project = await resolve_project(db, id)
    if current_user.role == UserRole.DONOR:
        raise ForbiddenException("Donors do not have access to internal risk assessments.")
    if current_user.role == UserRole.NGO and project.ngo_id != current_user.ngo_id:
        raise ForbiddenException("You do not have permission to view risk analysis for this project.")

    engine = get_risk_engine()
    report = await engine.evaluate_project_risk(db, project)

    return ok(
        report.model_dump(mode="json"),
        message="Project risk assessment evaluated successfully.",
    )


@router.post("/projects/{id}/evaluate", response_model=dict)
async def evaluate_project_risk_endpoint(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """Force real-time re-evaluation of project risk factors. Restricted to owning NGO, Auditors, and Admins."""
    from app.auth.models import UserRole
    from app.core.exceptions import ForbiddenException

    project = await resolve_project(db, id)
    if current_user.role == UserRole.DONOR:
        raise ForbiddenException("Donors cannot trigger project risk evaluations.")
    if current_user.role == UserRole.NGO and project.ngo_id != current_user.ngo_id:
        raise ForbiddenException("You do not have permission to evaluate risk for this project.")

    engine = get_risk_engine()
    report = await engine.evaluate_project_risk(db, project)

    return ok(
        report.model_dump(mode="json"),
        message="Project risk assessment re-evaluated.",
    )


@router.get("/projects/{id}/integrity-flags", response_model=dict)
async def get_project_integrity_flags(
    id: str,
    current_user: CurrentUserDep,
    db: DbDep,
):
    """
    Retrieve comprehensive 10-threat anti-manipulation integrity report and active flags.
    Restricted to project owning NGO, platform Auditors, and Admins.
    """
    from app.auth.models import UserRole
    from app.core.exceptions import ForbiddenException
    from app.risk.integrity_service import get_integrity_service

    project = await resolve_project(db, id)
    if current_user.role == UserRole.DONOR:
        raise ForbiddenException("Donors do not have access to internal anti-manipulation integrity flags.")
    if current_user.role == UserRole.NGO and project.ngo_id != current_user.ngo_id:
        raise ForbiddenException("You do not have permission to view integrity flags for this project.")

    service = get_integrity_service()
    report = await service.generate_project_integrity_report(db, project)

    return ok(
        report.model_dump(mode="json"),
        message="Project integrity flags evaluated successfully.",
    )
