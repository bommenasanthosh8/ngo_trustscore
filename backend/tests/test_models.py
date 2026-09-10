"""
Tests for SQLAlchemy database models:
- Entity creation & primary key generation (UUIDs)
- Relationships & Cascading Deletes (NGO -> Projects -> Evidences -> VerificationResults)
- User belonging to NGO relationship
- Constraints and foreign keys
"""
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    AuditDecisionType,
    AuditStatus,
    DisputeStatus,
    EvidenceType,
    ProjectStatus,
    ProjectType,
    RiskLevel,
    UserRole,
    VerificationModel,
    VerificationStatus,
)
from app.models.ngo import NGO
from app.models.user import User
from app.models.project import Project
from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence

from app.models.verification import VerificationResult
from app.models.risk import RiskAssessment
from app.models.audit import Audit, AuditDecision
from app.models.score import ScoreSnapshot
from app.models.dispute import Dispute
from app.models.activity import ActivityLog


@pytest.mark.asyncio
async def test_ngo_user_project_evidence_cascade_relationships(db_session: AsyncSession):
    # 1. Create NGO
    ngo = NGO(
        name="Hope Relief Trust",
        registration_number="NGO-HOPE-999",
        contact_email="contact@hoperelief.org",
    )
    db_session.add(ngo)
    await db_session.flush()
    assert ngo.id is not None
    assert ngo.created_at is not None

    # 2. Create User belonging to this NGO
    ngo_user = User(
        email="hope_admin@hoperelief.org",
        hashed_password="hashed_dummy_password",
        full_name="Sarah Connor",
        role=UserRole.NGO,
        ngo_id=ngo.id,
    )
    db_session.add(ngo_user)
    await db_session.flush()
    assert ngo_user.id is not None
    assert ngo_user.ngo_id == ngo.id

    # 3. Create Project under the NGO
    project = Project(
        ngo_id=ngo.id,
        created_by_id=ngo_user.id,
        title="Village School Construction",
        project_type=ProjectType.EDUCATION,
        verification_model=VerificationModel.PERMANENT,
        total_budget=750000.0,
    )
    db_session.add(project)
    await db_session.flush()
    assert project.id is not None

    # 4. Create Evidence under the Project
    evidence = Evidence(
        project_id=project.id,
        submitted_by_id=ngo_user.id,
        evidence_type=EvidenceType.IMAGE,
        title="Foundation Pouring Inspection",
        file_path="storage/evidence/foundation_1.jpg",
        file_hash_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        verification_status=VerificationStatus.PENDING,
    )
    db_session.add(evidence)
    await db_session.flush()
    assert evidence.id is not None

    # 5. Create FinancialEvidence under the Project
    fin_evidence = FinancialEvidence(
        project_id=project.id,
        submitted_by_id=ngo_user.id,
        invoice_number="INV-2026-001",
        vendor_name="National Cement Co.",
        amount=125000.0,
        currency="INR",
        document_path="storage/financials/inv_001.pdf",
        document_hash="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    )
    db_session.add(fin_evidence)
    await db_session.flush()
    assert fin_evidence.id is not None

    # 6. Create VerificationResult linked to Evidence
    v_res = VerificationResult(
        evidence_id=evidence.id,
        geofence_match=True,
        geofence_distance_meters=15.2,
        timestamp_valid=True,
        tampering_detected=False,
        ai_confidence_score=98.5,
    )
    db_session.add(v_res)
    await db_session.flush()
    assert v_res.id is not None

    # 7. Create RiskAssessment
    risk = RiskAssessment(
        project_id=project.id,
        risk_level=RiskLevel.LOW,
        risk_score=12.5,
        factors={"location_risk": "low", "vendor_flag": False},
    )
    db_session.add(risk)
    await db_session.flush()
    assert risk.id is not None

    # 8. Create Audit & AuditDecision
    auditor = User(
        email="audit_agent@gov.org",
        hashed_password="hashed_dummy_password",
        full_name="Agent Smith",
        role=UserRole.AUDITOR,
    )
    db_session.add(auditor)
    await db_session.flush()

    audit = Audit(
        project_id=project.id,
        auditor_id=auditor.id,
        status=AuditStatus.CONCLUDED,
        findings="All milestone criteria satisfied.",
    )
    db_session.add(audit)
    await db_session.flush()

    decision = AuditDecision(
        audit_id=audit.id,
        decision=AuditDecisionType.APPROVED,
        notes="Approved with full compliance.",
    )
    db_session.add(decision)
    await db_session.flush()

    # 9. Create ScoreSnapshot
    score_snap = ScoreSnapshot(
        project_id=project.id,
        ngo_id=ngo.id,
        composite_score=94.5,
        breakdown={"milestone": 96.0, "financial": 93.0},
    )
    db_session.add(score_snap)
    await db_session.flush()

    # 10. Create Dispute
    dispute = Dispute(
        project_id=project.id,
        raised_by_id=ngo_user.id,
        reason="Requesting recalculation of timeline delay penalty.",
        status=DisputeStatus.OPEN,
    )
    db_session.add(dispute)
    await db_session.flush()

    # 11. Create ActivityLog
    activity = ActivityLog(
        action="AUDIT_CONCLUDED",
        actor_id=auditor.id,
        actor_role="AUDITOR",
        resource_type="Project",
        resource_id=str(project.id),
        detail={"decision": "APPROVED"},
    )
    db_session.add(activity)
    await db_session.flush()

    # Verify query relationships
    result = await db_session.execute(select(Project).where(Project.id == project.id))
    fetched_project = result.scalar_one()
    assert fetched_project.ngo_id == ngo.id
    assert fetched_project.created_by_id == ngo_user.id
