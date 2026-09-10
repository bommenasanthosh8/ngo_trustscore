"""
Pydantic schemas for the Independent Audit Module.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.enums import (
    AuditDecisionType,
    AuditSelectionReason,
    AuditStatus,
    DisputeStatus,
    ProjectStatus,
    ProjectType,
    VerificationModel,
)
from app.schemas.evidence import EvidenceTimelineItem
from app.schemas.financial_evidence import FinancialConsistencyReport, FinancialEvidenceResponse
from app.schemas.integrity import ProjectIntegrityReportResponse
from app.schemas.risk import RiskAssessmentResponse
from app.schemas.verification import VerificationReportResponse


class AuditDecisionCreateRequest(BaseModel):
    """Payload for submitting an immutable auditor decision."""
    decision: AuditDecisionType
    findings: str = Field(..., min_length=5, description="Auditor findings regarding project delivery (mandatory)")
    notes: Optional[str] = Field(None, description="Detailed explanatory notes")
    supporting_evidence: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Links, references, or uploaded file identifiers supporting the decision",
    )


class AuditDecisionResponse(BaseModel):
    """Standardized representation of an immutable audit decision."""
    id: uuid.UUID
    audit_id: uuid.UUID
    decision: AuditDecisionType
    findings: Optional[str] = None
    notes: Optional[str] = None
    supporting_evidence: Optional[Dict[str, Any]] = None
    is_superseded: bool
    superseded_by_id: Optional[uuid.UUID] = None
    decided_by_id: Optional[uuid.UUID] = None
    decided_at: datetime


class AuditSummaryResponse(BaseModel):
    """Lightweight representation of an audit queue item."""
    id: uuid.UUID
    project_id: uuid.UUID
    project_code: str
    project_title: str
    project_category: ProjectType
    project_status: ProjectStatus
    target_amount: float
    ngo_id: Optional[uuid.UUID] = None
    ngo_name: Optional[str] = None
    auditor_id: Optional[uuid.UUID] = None
    auditor_name: Optional[str] = None
    status: AuditStatus
    selection_reason: AuditSelectionReason
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    created_at: datetime
    latest_decision: Optional[AuditDecisionType] = None


class AuditDossierResponse(BaseModel):
    """Comprehensive auditor view assembling all evidence, telemetry, and claims."""
    audit_id: uuid.UUID
    status: AuditStatus
    selection_reason: AuditSelectionReason
    created_at: datetime
    scope: Optional[str] = None

    # 1. Project details & location
    project_id: uuid.UUID
    project_code: str
    project_title: str
    project_category: ProjectType
    verification_model: VerificationModel
    project_status: ProjectStatus
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geofence_radius: float

    # 2. NGO claim
    ngo_id: uuid.UUID
    ngo_name: str
    target_amount: float
    total_budget: float
    expected_beneficiaries: int
    project_description: Optional[str] = None
    start_date: Optional[datetime] = None
    expected_completion_date: Optional[datetime] = None

    # 3. Evidence timeline & files
    evidence_timeline: List[EvidenceTimelineItem] = Field(default_factory=list)

    # 4. Financial evidence & consistency
    financial_evidence: List[FinancialEvidenceResponse] = Field(default_factory=list)
    financial_consistency: Optional[FinancialConsistencyReport] = None

    # 5. Verification results (10 checks)
    verification_report: Optional[VerificationReportResponse] = None

    # 6. Risk assessment & narrative reasons
    risk_assessment: Optional[RiskAssessmentResponse] = None

    # 7. Authoritative calculated evidence score
    evidence_score: Optional[float] = None
    evidence_score_status: Optional[str] = None
    evidence_score_breakdown: Optional[Dict[str, Any]] = None

    # 8. Decisions history & disputes
    decisions_history: List[AuditDecisionResponse] = Field(default_factory=list)
    disputes: List[DisputeResponse] = Field(default_factory=list)

    # 9. Anti-Manipulation & Integrity Evaluation
    integrity_report: Optional[ProjectIntegrityReportResponse] = None


class AuditQueueGroupResponse(BaseModel):
    """Auditor queue categorized into distinct operational buckets."""
    pending_audits: List[AuditSummaryResponse] = Field(default_factory=list)
    high_risk: List[AuditSummaryResponse] = Field(default_factory=list)
    high_value: List[AuditSummaryResponse] = Field(default_factory=list)
    random_queue: List[AuditSummaryResponse] = Field(default_factory=list)
    disputed: List[AuditSummaryResponse] = Field(default_factory=list)
    recently_verified: List[AuditSummaryResponse] = Field(default_factory=list)
    counts: Dict[str, int] = Field(default_factory=dict)


class CreateDisputeRequest(BaseModel):
    """Request from NGO to review an audit."""
    reason: str = Field(..., min_length=10, max_length=5000, description="Detailed reason for disputing the audit")
    supporting_notes: Optional[str] = None


class DisputeResponse(BaseModel):
    """Dispute record representation."""
    id: uuid.UUID
    project_id: uuid.UUID
    project_code: Optional[str] = None
    raised_by_id: uuid.UUID
    reason: str
    status: DisputeStatus
    resolution_notes: Optional[str] = None
    created_at: datetime


class ResolveDisputeRequest(BaseModel):
    """Admin payload to resolve an audit dispute."""
    resolution_notes: str = Field(..., min_length=5)
    action: str = Field(..., description="UPHOLD_DECISION | REVISE_DECISION | SCHEDULE_REAUDIT")
    revised_decision: Optional[AuditDecisionType] = None
    revised_findings: Optional[str] = None


class InitiateAuditRequest(BaseModel):
    """Request to initiate or assign an audit for a project."""
    project_id: uuid.UUID
    scope: Optional[str] = None
    selection_reason: Optional[AuditSelectionReason] = AuditSelectionReason.MANUAL_ASSIGNMENT
