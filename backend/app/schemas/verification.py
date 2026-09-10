"""
Pydantic schemas for the Evidence Verification Engine.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.enums import RecommendedAction


class CheckResultSchema(BaseModel):
    check_name: str
    status: str
    score: float
    explanation: str
    risk_flags: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class VerificationReportResponse(BaseModel):
    project_id: uuid.UUID
    project_code: str
    overall_score: float
    overall_quality: str
    recommended_action: RecommendedAction
    risk_flags: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    individual_checks: List[CheckResultSchema]
    evaluated_at: datetime
    evidence_count: int
    financial_evidence_count: int
    target_evidence_id: Optional[uuid.UUID] = None


class VerificationTriggerRequest(BaseModel):
    force_reevaluate: bool = True
