"""
Score Service layer.

Provides orchestration for calculating, retrieving, and logging project evidence scores.
Strictly backend-authoritative: no arbitrary client score submissions allowed.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.models.audit import Audit
from app.models.ngo import NGO
from app.models.project import Project
from app.models.score import ScoreSnapshot
from app.schemas.score import (
    NGOTransparencyScoreResponse,
    ProjectScoreResponse,
)
from app.scores.engine import get_score_engine
from app.scores.ngo_engine import (
    NGOTransparencyScoreWeights,
    get_ngo_score_engine,
)


async def get_or_calculate_project_score(
    db: AsyncSession,
    project_id_or_code: str,
    force_recalculate: bool = False,
) -> ProjectScoreResponse:
    """
    Retrieve current authoritative score for a project, computing it if not yet calculated
    or if forced recalculation is requested.
    """
    # 1. Resolve project
    proj_query = select(Project).options(
        selectinload(Project.ngo),
        selectinload(Project.disputes),
        selectinload(Project.audits).selectinload(Audit.decisions),
    )

    try:
        proj_uuid = uuid.UUID(project_id_or_code)
        proj_query = proj_query.where(Project.id == proj_uuid)
    except (ValueError, TypeError):
        proj_query = proj_query.where(Project.project_code == project_id_or_code)

    res = await db.execute(proj_query)
    project = res.scalar_one_or_none()

    if not project:
        raise NotFoundException(f"Project '{project_id_or_code}'")

    engine = get_score_engine()
    # Calculate score and record snapshot
    return await engine.calculate_score(db, project, record_snapshot=True)


async def list_score_snapshots(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> List[ScoreSnapshot]:
    """Retrieve chronological history of score snapshots for a project."""
    stmt = (
        select(ScoreSnapshot)
        .where(ScoreSnapshot.project_id == project_id)
        .order_by(ScoreSnapshot.calculated_at.desc())
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def get_or_calculate_ngo_score(
    db: AsyncSession,
    ngo_id: uuid.UUID,
    weights_override: Optional[NGOTransparencyScoreWeights] = None,
    record_snapshot: bool = True,
) -> NGOTransparencyScoreResponse:
    """
    Retrieve or calculate authoritative NGO Transparency Score across its project portfolio.
    """
    ngo = await db.get(NGO, ngo_id)
    if not ngo:
        raise NotFoundException(f"NGO '{ngo_id}'")

    engine = get_ngo_score_engine()
    return await engine.calculate_score(
        db,
        ngo,
        weights_override=weights_override,
        record_snapshot=record_snapshot,
    )


async def list_ngo_score_snapshots(
    db: AsyncSession,
    ngo_id: uuid.UUID,
) -> List[ScoreSnapshot]:
    """
    Retrieve chronological history of score snapshots for an NGO.
    Filters exclusively for NGO-level portfolio snapshots (project_id IS NULL).
    """
    stmt = (
        select(ScoreSnapshot)
        .where(
            ScoreSnapshot.ngo_id == ngo_id,
            ScoreSnapshot.project_id.is_(None),
        )
        .order_by(ScoreSnapshot.calculated_at.desc())
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())

