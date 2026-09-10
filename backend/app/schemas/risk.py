"""
Pydantic schemas for the Risk Assessment Engine.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.enums import RiskLevel


class RiskSignalResult(BaseModel):
    """Output evaluation of an individual risk signal."""
    signal_name: str
    triggered: bool
    weight: float
    score_contribution: float
    explanation: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class AuditTriggerInfo(BaseModel):
    """Audit recommendation triggers determined by risk score and sampling."""
    audit_recommended: bool
    triggers: List[str] = Field(default_factory=list)
    trigger_reasons: List[str] = Field(default_factory=list)


class RiskAssessmentResponse(BaseModel):
    """Complete project risk assessment report."""
    project_id: uuid.UUID
    project_code: str
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Risk score clamped to 0–100")
    risk_level: RiskLevel = Field(..., description="LOW (0-29), MEDIUM (30-59), HIGH (60-100)")
    reasons: List[str] = Field(default_factory=list, description="Narrative bullet explanations of active risk factors")
    signals: List[RiskSignalResult] = Field(default_factory=list)
    audit_trigger: AuditTriggerInfo
    assessed_at: datetime
    factors_summary: Dict[str, Any] = Field(default_factory=dict)


class RiskEvaluationRequest(BaseModel):
    force_reevaluate: bool = True
