"""
Pydantic schemas for the Project Evidence Score Engine.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.enums import DisputeStatus, ScoreStatus


class ScoreFactorResult(BaseModel):
    """Result of an individual scoring dimension."""
    factor_name: str
    earned_points: float = Field(..., description="Points earned for this factor")
    maximum_points: float = Field(..., description="Maximum possible points for this factor")
    percentage: float = Field(..., description="Earned points as percentage of maximum")
    explanation: str = Field(..., description="Narrative rationale for factor score")
    source_verification_results: Dict[str, Any] = Field(
        default_factory=dict,
        description="Reference verification check data and metrics",
    )


class ProjectScoreResponse(BaseModel):
    """Authoritative project evidence score response."""
    project_id: uuid.UUID
    project_code: str
    project_title: str
    final_score: float = Field(..., ge=0.0, le=100.0, description="Composite score out of 100")
    status: ScoreStatus = Field(..., description="STRONG_EVIDENCE | GOOD_EVIDENCE | LIMITED_EVIDENCE | WEAK_EVIDENCE")
    is_disputed: bool = Field(default=False, description="Whether this project is currently in dispute")
    dispute_status: Optional[DisputeStatus] = Field(default=None, description="Active dispute status if applicable")
    explanation: str = Field(..., description="Comprehensive summary explanation of evidence strength")
    factors: Dict[str, ScoreFactorResult] = Field(
        ...,
        description="Detailed score breakdown across all 6 evidence dimensions",
    )
    calculated_at: datetime


class NGOTransparencyFactor(BaseModel):
    """Result of an individual NGO scoring dimension."""
    factor_name: str
    weight: float = Field(..., description="Configured weight for this dimension (0.0 to 1.0)")
    raw_score: float = Field(..., ge=0.0, le=100.0, description="Raw score for this dimension (0 to 100)")
    weighted_score: float = Field(..., description="Dimension contribution to final score (raw_score * weight)")
    explanation: str = Field(..., description="Narrative rationale for this dimension")
    details: Dict[str, Any] = Field(default_factory=dict, description="Supporting metrics and statistics")


class NGOTransparencyScoreResponse(BaseModel):
    """Authoritative NGO Transparency Score response."""
    ngo_id: uuid.UUID
    ngo_name: str
    final_score: float = Field(..., ge=0.0, le=100.0, description="Composite transparency score out of 100")
    indicator_description: str = Field(
        default="Evidence-based transparency/verification indicator.",
        description="Standard explanation label",
    )
    project_count: int = Field(..., ge=0, description="Total projects associated with this NGO")
    verified_count: int = Field(..., ge=0, description="Count of fully verified projects")
    partially_verified_count: int = Field(..., ge=0, description="Count of partially verified projects")
    pending_count: int = Field(..., ge=0, description="Count of projects under verification or pending")
    disputed_count: int = Field(..., ge=0, description="Count of disputed projects")
    weighted_evidence_quality: float = Field(..., ge=0.0, le=100.0, description="Value-weighted average project evidence score (0-100)")
    audit_performance: float = Field(..., ge=0.0, le=100.0, description="Independent audit performance score (0-100)")
    historical_trend: str = Field(..., description="IMPROVING | STABLE | DECLINING | INSUFFICIENT_DATA")
    explanation: List[str] = Field(..., description="Explainable bullet points for user interface")
    factors: Dict[str, NGOTransparencyFactor] = Field(
        ...,
        description="Detailed breakdown across all scoring dimensions",
    )
    calculated_at: datetime
    snapshot_id: Optional[uuid.UUID] = Field(default=None, description="Persisted ScoreSnapshot record ID")


class NGOScoreSnapshotResponse(BaseModel):
    """Historical score snapshot record."""
    id: uuid.UUID
    ngo_id: uuid.UUID
    composite_score: float
    breakdown: Optional[Dict[str, Any]] = None
    calculated_at: datetime

