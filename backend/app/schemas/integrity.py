"""
Integrity & Anti-Manipulation Schemas.

Data contracts for the 10-threat defense layer, integrity flags,
submission attempt histories, and prototype transparency disclaimers.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IntegrityFlagItem(BaseModel):
    """High-visibility integrity warning flag."""
    severity: str = Field(..., description="HIGH | MEDIUM | LOW")
    title: str = Field(..., description="E.g. Evidence reused across projects")
    explanation: str
    signal_code: str


class ThreatEvaluation(BaseModel):
    """Evaluation result for one of the 10 threat vectors."""
    threat_number: int
    threat_name: str
    severity: str = Field(..., description="HIGH | MEDIUM | LOW")
    triggered: bool
    status: str = Field(..., description="CLEAR | WARNING | FLAGGED")
    explanation: str
    is_probabilistic_signal: bool = False
    disclaimer: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class SubmissionAttemptSummary(BaseModel):
    """Forensic summary of evidence submission attempts."""
    total_submissions: int = 0
    verified_count: int = 0
    failed_count: int = 0
    duplicate_count: int = 0
    revisions_count: int = 0
    superseded_count: int = 0


class ProjectIntegrityReportResponse(BaseModel):
    """Comprehensive integrity report exposing all potential manipulation attempts."""
    project_id: uuid.UUID
    project_code: str
    project_title: str
    overall_risk_level: str = Field(..., description="LOW | MEDIUM | HIGH | CRITICAL")
    risk_score: float = Field(..., ge=0.0, le=100.0)
    audit_recommended: bool

    # Prominent warning flags
    active_flags: List[IntegrityFlagItem] = Field(default_factory=list)

    # 10-Threat Defense Matrix
    threats_matrix: List[ThreatEvaluation] = Field(default_factory=list)

    # Submission Attempt History
    submission_history: SubmissionAttemptSummary

    # Prototype Transparency Disclaimers
    disclaimers: List[str] = Field(default_factory=list)
