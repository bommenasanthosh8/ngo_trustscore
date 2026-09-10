"""
Admin Schemas.

Schemas for audit configuration, dispute administration, activity logging, and platform KPIs.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.enums import AuditSelectionReason, AuditStatus, DisputeStatus, ProjectStatus, VerificationStatus


class AuditConfigResponse(BaseModel):
    high_project_value_threshold: float
    audit_random_sample_rate: float
    high_risk_threshold: float
    auto_audit_enabled: bool = True
    scoring_weights: Dict[str, float] = Field(default_factory=dict)
    updated_at: Optional[datetime] = None


class AuditConfigUpdateRequest(BaseModel):
    high_project_value_threshold: Optional[float] = Field(None, ge=0.0)
    audit_random_sample_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    high_risk_threshold: Optional[float] = Field(None, ge=0.0, le=100.0)
    auto_audit_enabled: Optional[bool] = None


class AdminDisputeItemResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_code: Optional[str] = None
    project_title: Optional[str] = None
    ngo_name: Optional[str] = None
    raised_by_id: uuid.UUID
    raised_by_email: Optional[str] = None
    reason: str
    status: DisputeStatus
    resolution_notes: Optional[str] = None
    created_at: datetime


class ActivityLogResponse(BaseModel):
    id: uuid.UUID
    action: str
    actor_id: Optional[uuid.UUID] = None
    actor_role: Optional[str] = None
    actor_email: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None
    success: bool
    ip_address: Optional[str] = None
    created_at: datetime


class SystemStatsResponse(BaseModel):
    ngos: Dict[str, int]
    projects: Dict[str, int]
    audits: Dict[str, int]
    disputes: Dict[str, int]
    total_funding_volume: float
    avg_transparency_score: float
    generated_at: datetime
