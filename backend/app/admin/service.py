"""
Admin Service.

Business logic for platform governance, audit threshold configuration,
dispute reviews, activity log retrieval, and platform KPIs.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.activity import ActivityLog
from app.models.audit import Audit
from app.models.dispute import Dispute
from app.models.enums import AuditSelectionReason, AuditStatus, DisputeStatus, ProjectStatus, VerificationStatus
from app.models.ngo import NGO
from app.models.project import Project
from app.models.score import ScoreSnapshot
from app.models.user import User
from app.schemas.admin import (
    ActivityLogResponse,
    AdminDisputeItemResponse,
    AuditConfigResponse,
    AuditConfigUpdateRequest,
    SystemStatsResponse,
)

logger = logging.getLogger(__name__)

# Dynamic runtime configuration store initialized from application Settings
_runtime_audit_config: Dict[str, Any] = {
    "high_project_value_threshold": None,  # Will fall back to settings
    "audit_random_sample_rate": None,
    "high_risk_threshold": 60.0,
    "auto_audit_enabled": True,
    "updated_at": None,
}


def get_audit_config() -> AuditConfigResponse:
    """Retrieve current platform audit configuration."""
    settings = get_settings()
    high_val = (
        _runtime_audit_config["high_project_value_threshold"]
        if _runtime_audit_config["high_project_value_threshold"] is not None
        else settings.HIGH_PROJECT_VALUE_THRESHOLD
    )
    sample_rate = (
        _runtime_audit_config["audit_random_sample_rate"]
        if _runtime_audit_config["audit_random_sample_rate"] is not None
        else settings.AUDIT_RANDOM_SAMPLE_RATE
    )
    risk_thresh = _runtime_audit_config["high_risk_threshold"]
    auto_enabled = _runtime_audit_config["auto_audit_enabled"]
    updated_at = _runtime_audit_config["updated_at"]

    scoring_weights = {
        "location": settings.SCORE_LOCATION_WEIGHT,
        "timeline": settings.SCORE_TIMELINE_WEIGHT,
        "media": settings.SCORE_MEDIA_WEIGHT,
        "financial": settings.SCORE_FINANCIAL_WEIGHT,
        "identity": settings.SCORE_IDENTITY_WEIGHT,
        "audit": settings.SCORE_AUDIT_WEIGHT,
    }

    return AuditConfigResponse(
        high_project_value_threshold=float(high_val),
        audit_random_sample_rate=float(sample_rate),
        high_risk_threshold=float(risk_thresh),
        auto_audit_enabled=bool(auto_enabled),
        scoring_weights=scoring_weights,
        updated_at=updated_at,
    )


def update_audit_config(payload: AuditConfigUpdateRequest) -> AuditConfigResponse:
    """Update runtime platform audit configuration."""
    now_utc = datetime.now(timezone.utc)
    if payload.high_project_value_threshold is not None:
        _runtime_audit_config["high_project_value_threshold"] = payload.high_project_value_threshold
    if payload.audit_random_sample_rate is not None:
        _runtime_audit_config["audit_random_sample_rate"] = payload.audit_random_sample_rate
    if payload.high_risk_threshold is not None:
        _runtime_audit_config["high_risk_threshold"] = payload.high_risk_threshold
    if payload.auto_audit_enabled is not None:
        _runtime_audit_config["auto_audit_enabled"] = payload.auto_audit_enabled

    _runtime_audit_config["updated_at"] = now_utc
    return get_audit_config()


async def list_all_disputes(
    db: AsyncSession,
    status_filter: Optional[DisputeStatus] = None,
) -> List[AdminDisputeItemResponse]:
    """List all project audit disputes across the platform."""
    q = (
        select(Dispute)
        .options(
            selectinload(Dispute.project).selectinload(Project.ngo),
            selectinload(Dispute.raised_by),
        )
        .order_by(Dispute.created_at.desc())
    )
    if status_filter:
        q = q.where(Dispute.status == status_filter)

    res = await db.execute(q)
    disputes = res.scalars().all()

    items: List[AdminDisputeItemResponse] = []
    for d in disputes:
        proj = d.project
        ngo_name = proj.ngo.name if (proj and proj.ngo) else "Unknown NGO"
        items.append(
            AdminDisputeItemResponse(
                id=d.id,
                project_id=d.project_id,
                project_code=proj.project_code if proj else None,
                project_title=proj.title if proj else None,
                ngo_name=ngo_name,
                raised_by_id=d.raised_by_id,
                raised_by_email=d.raised_by.email if d.raised_by else None,
                reason=d.reason,
                status=d.status,
                resolution_notes=d.resolution_notes,
                created_at=d.created_at,
            )
        )
    return items


async def list_activity_logs(
    db: AsyncSession,
    action: Optional[str] = None,
    actor_role: Optional[str] = None,
    resource_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[ActivityLogResponse]:
    """Retrieve immutable system audit logs with optional filtering."""
    q = (
        select(ActivityLog, User.email)
        .outerjoin(User, ActivityLog.actor_id == User.id)
        .order_by(ActivityLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if action:
        q = q.where(ActivityLog.action == action)
    if actor_role:
        q = q.where(ActivityLog.actor_role == actor_role)
    if resource_type:
        q = q.where(ActivityLog.resource_type == resource_type)

    res = await db.execute(q)
    rows = res.all()

    logs: List[ActivityLogResponse] = []
    for log, user_email in rows:
        logs.append(
            ActivityLogResponse(
                id=log.id,
                action=log.action,
                actor_id=log.actor_id,
                actor_role=log.actor_role,
                actor_email=user_email,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                detail=log.detail,
                success=log.success,
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
        )
    return logs


async def get_system_stats(db: AsyncSession) -> SystemStatsResponse:
    """Aggregate platform governance metrics across NGOs, Projects, Audits, and Scores."""
    # 1. NGO statistics
    ngo_res = await db.execute(
        select(NGO.verification_status, func.count(NGO.id)).group_by(NGO.verification_status)
    )
    ngo_counts = {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in ngo_res.all()}
    ngo_total = sum(ngo_counts.values())
    ngo_counts["TOTAL"] = ngo_total

    # 2. Project statistics & total funding
    proj_res = await db.execute(
        select(Project.status, func.count(Project.id), func.sum(Project.target_amount)).group_by(Project.status)
    )
    proj_rows = proj_res.all()
    proj_counts = {}
    total_funding = 0.0
    for status, count, funding in proj_rows:
        key = str(status.value if hasattr(status, 'value') else status)
        proj_counts[key] = count
        if funding:
            total_funding += float(funding)
    proj_counts["TOTAL"] = sum(proj_counts.values())

    # 3. Audit statistics
    audit_res = await db.execute(
        select(Audit.status, func.count(Audit.id)).group_by(Audit.status)
    )
    audit_counts = {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in audit_res.all()}
    audit_counts["TOTAL"] = sum(audit_counts.values())

    # 4. Dispute statistics
    disp_res = await db.execute(
        select(Dispute.status, func.count(Dispute.id)).group_by(Dispute.status)
    )
    disp_counts = {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in disp_res.all()}
    disp_counts["TOTAL"] = sum(disp_counts.values())

    # 5. Average transparency score
    score_res = await db.execute(
        select(func.avg(ScoreSnapshot.composite_score))
    )
    avg_score = score_res.scalar() or 75.0

    return SystemStatsResponse(
        ngos=ngo_counts,
        projects=proj_counts,
        audits=audit_counts,
        disputes=disp_counts,
        total_funding_volume=round(total_funding, 2),
        avg_transparency_score=round(float(avg_score), 1),
        generated_at=datetime.now(timezone.utc),
    )
