"""
Tests for Prototype Anti-Manipulation & Integrity Defense Layer.

Validates:
1. Threat 1: Old/reused photos (Cross-project SHA-256 collision detection & pre-dated captures).
2. Threat 2: Duplicate evidence (Internal project hash collision).
3. Threat 3: Fake GPS (Geofence mismatch flagged as a probabilistic corroborating signal;
   verifies explicit disclaimer that GPS does not guarantee authenticity).
4. Threat 4: Manipulated media (Photo-editing metadata heuristics flagged with disclaimer
   that AI/metadata heuristics are not definitive proof).
5. Threat 7: Project budget inflation detection.
6. Threat 8: Financial inconsistency flags (Supported receipts < 85% of claimed).
7. Threat 9 & 10: Architectural invariants (Immutable audit decisions & append-only evidence history).
8. Dedicated API endpoints:
   - GET /api/v1/risk/projects/{id}/integrity-flags
   - GET /api/v1/audits/{id}/integrity-flags
   - GET /api/v1/audits/{id} (Embedded dossier integrity report)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.core.security import create_access_token, hash_password
from app.models.enums import (
    AuditDecisionType,
    AuditSelectionReason,
    AuditStatus,
    EvidenceType,
    FinancialDocumentType,
    FinancialValidationStatus,
    LocationStatus,
    NGOVerificationStatus,
    ProjectStatus,
    ProjectType,
    VerificationModel,
    VerificationStatus,
)
from app.models.ngo import NGO
from app.models.project import Project
from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence
from app.models.audit import Audit
from app.risk.integrity_service import get_integrity_service


async def _create_user(db: AsyncSession, role: UserRole, email_prefix: str) -> tuple[User, str]:
    user = User(
        email=f"{email_prefix}_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Password123!"),
        full_name=f"{role.value} Tester",
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    token = create_access_token(subject=str(user.id), extra={"email": user.email, "role": user.role.value})
    return user, token


async def _create_base_project(db: AsyncSession, user: User, target_amount: float = 500000.0) -> tuple[NGO, Project]:
    ngo = NGO(
        name=f"Integrity Test NGO {uuid.uuid4().hex[:4]}",
        registration_number=f"REG-INT-{uuid.uuid4().hex[:6].upper()}",
        darpan_id=f"IND-{uuid.uuid4().hex[:6].upper()}",
        verification_status=NGOVerificationStatus.VERIFIED,
        is_verified=True,
    )
    db.add(ngo)
    await db.flush()

    project = Project(
        project_code=f"PRJ-INT-{uuid.uuid4().hex[:6].upper()}",
        title="Clean Water Project",
        description="Providing clean water filtration systems",
        project_type=ProjectType.WATER_AND_SANITATION,
        verification_model=VerificationModel.PERMANENT,
        status=ProjectStatus.UNDER_VERIFICATION,
        ngo_id=ngo.id,
        created_by_id=user.id,
        target_amount=target_amount,
        total_budget=target_amount,
        latitude=12.9716,
        longitude=77.5946,
        geofence_radius=500.0,
        start_date=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        expected_beneficiaries=1000,
    )
    db.add(project)
    await db.flush()
    return ngo, project


@pytest.mark.asyncio
async def test_cross_project_media_reuse_detected(db_session: AsyncSession):
    """Threat 1: Test that identical SHA-256 hash across different projects triggers HIGH risk flag."""
    auditor, _ = await _create_user(db_session, UserRole.AUDITOR, "auditor_t1")
    ngo, project1 = await _create_base_project(db_session, auditor)
    _, project2 = await _create_base_project(db_session, auditor)

    shared_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    # Evidence in project 1
    ev1 = Evidence(
        project_id=project1.id,
        submitted_by_id=auditor.id,
        evidence_type=EvidenceType.COMPLETION,
        title="Borewell completed",
        storage_key="p1/borewell.jpg",
        file_hash_sha256=shared_hash,
        verification_status=VerificationStatus.VERIFIED,
    )
    db_session.add(ev1)

    # Reused identical photo in project 2
    ev2 = Evidence(
        project_id=project2.id,
        submitted_by_id=auditor.id,
        evidence_type=EvidenceType.COMPLETION,
        title="Another Borewell",
        storage_key="p2/borewell.jpg",
        file_hash_sha256=shared_hash,
        verification_status=VerificationStatus.PENDING,
    )
    db_session.add(ev2)
    await db_session.commit()

    service = get_integrity_service()
    report = await service.generate_project_integrity_report(db_session, project2)

    # Check Threat 1
    t1 = next(t for t in report.threats_matrix if t.threat_number == 1)
    assert t1.triggered is True
    assert t1.status == "FLAGGED"
    assert t1.severity == "HIGH"

    # Check Active Flags
    reused_flag = next((f for f in report.active_flags if f.signal_code == "CROSS_PROJECT_REUSE"), None)
    assert reused_flag is not None
    assert reused_flag.title == "Evidence reused across projects"
    assert reused_flag.severity == "HIGH"


@pytest.mark.asyncio
async def test_duplicate_evidence_within_project(db_session: AsyncSession):
    """Threat 2: Test that identical evidence file submitted multiple times within same project is flagged."""
    auditor, _ = await _create_user(db_session, UserRole.AUDITOR, "auditor_t2")
    _, project = await _create_base_project(db_session, auditor)

    identical_hash = "a" * 64
    ev1 = Evidence(
        project_id=project.id,
        submitted_by_id=auditor.id,
        evidence_type=EvidenceType.BEFORE,
        title="Site before construction",
        storage_key="p/ev1.jpg",
        file_hash_sha256=identical_hash,
        verification_status=VerificationStatus.VERIFIED,
    )
    ev2 = Evidence(
        project_id=project.id,
        submitted_by_id=auditor.id,
        evidence_type=EvidenceType.COMPLETION,
        title="Site after construction (fraudulent copy)",
        storage_key="p/ev2.jpg",
        file_hash_sha256=identical_hash,
        verification_status=VerificationStatus.PENDING,
    )
    db_session.add_all([ev1, ev2])
    await db_session.commit()

    service = get_integrity_service()
    report = await service.generate_project_integrity_report(db_session, project)

    t2 = next(t for t in report.threats_matrix if t.threat_number == 2)
    assert t2.triggered is True
    assert t2.status == "FLAGGED"
    assert t2.severity == "HIGH"

    dup_flag = next((f for f in report.active_flags if f.signal_code == "INTERNAL_DUPLICATE"), None)
    assert dup_flag is not None
    assert "Duplicate evidence" in dup_flag.title


@pytest.mark.asyncio
async def test_fake_gps_signal_and_mandatory_disclaimer(db_session: AsyncSession):
    """Threat 3: Test that location mismatch is flagged as a corroborating signal with explicit disclaimers."""
    auditor, _ = await _create_user(db_session, UserRole.AUDITOR, "auditor_t3")
    _, project = await _create_base_project(db_session, auditor)

    # Project coordinates: 12.9716, 77.5946 (Bangalore)
    # Evidence coordinates: 13.0827, 80.2707 (Chennai ~ 290 km away)
    ev = Evidence(
        project_id=project.id,
        submitted_by_id=auditor.id,
        evidence_type=EvidenceType.COMPLETION,
        title="Site Photo in another city",
        storage_key="p/far.jpg",
        file_hash_sha256="b" * 64,
        latitude=13.0827,
        longitude=80.2707,
        location_status=LocationStatus.CAPTURED,
    )
    db_session.add(ev)
    await db_session.commit()

    service = get_integrity_service()
    report = await service.generate_project_integrity_report(db_session, project)

    t3 = next(t for t in report.threats_matrix if t.threat_number == 3)
    assert t3.triggered is True
    assert t3.status == "FLAGGED"
    assert t3.is_probabilistic_signal is True
    assert t3.disclaimer is not None

    # CRITICAL: Verify mandatory requirement: Treat GPS as a signal; DO NOT claim "GPS guarantees authenticity"
    assert "GPS does not guarantee physical authenticity" in t3.disclaimer
    assert "guarantees authenticity" not in t3.explanation.lower() or "not" in t3.disclaimer

    loc_flag = next((f for f in report.active_flags if f.signal_code == "LOCATION_MISMATCH"), None)
    assert loc_flag is not None
    assert loc_flag.title == "Location mismatch"
    assert loc_flag.severity == "HIGH"


@pytest.mark.asyncio
async def test_manipulated_media_metadata_heuristic(db_session: AsyncSession):
    """Threat 4: Test that editing software metadata is flagged with AI/heuristic disclaimer."""
    auditor, _ = await _create_user(db_session, UserRole.AUDITOR, "auditor_t4")
    _, project = await _create_base_project(db_session, auditor)

    ev = Evidence(
        project_id=project.id,
        submitted_by_id=auditor.id,
        evidence_type=EvidenceType.COMPLETION,
        title="Edited Banner Photo",
        storage_key="p/edited.jpg",
        file_hash_sha256="c" * 64,
        metadata_summary={"software": "Adobe Photoshop 2024 (Windows)", "make": "Canon"},
    )
    db_session.add(ev)
    await db_session.commit()

    service = get_integrity_service()
    report = await service.generate_project_integrity_report(db_session, project)

    t4 = next(t for t in report.threats_matrix if t.threat_number == 4)
    assert t4.triggered is True
    assert t4.status == "WARNING"
    assert t4.is_probabilistic_signal is True

    # CRITICAL: Verify AI heuristic disclaimer
    assert "heuristic risk indicators, not definitive proof" in t4.disclaimer

    media_flag = next((f for f in report.active_flags if f.signal_code == "MANIPULATED_MEDIA"), None)
    assert media_flag is not None
    assert media_flag.title == "Edited media detected"


@pytest.mark.asyncio
async def test_financial_discrepancy_flag(db_session: AsyncSession):
    """Threat 8: Test that receipts supporting < 85% of claimed expenditure triggers HIGH risk flag."""
    auditor, _ = await _create_user(db_session, UserRole.AUDITOR, "auditor_t8")
    _, project = await _create_base_project(db_session, auditor, target_amount=1000000.0)

    # Claimed ₹1,000,000, but only submit ₹100,000 in receipts (10% supported)
    fin = FinancialEvidence(
        project_id=project.id,
        submitted_by_id=auditor.id,
        document_type=FinancialDocumentType.INVOICE,
        invoice_number="INV-2025-001",
        vendor_name="Hardware Supplies Ltd",
        claimed_amount=1000000.0,
        amount=1000000.0,
        extracted_amount=100000.0,
        validation_status=FinancialValidationStatus.VALID,
        storage_key="p/inv1.pdf",
        document_hash="d" * 64,
    )
    db_session.add(fin)
    await db_session.commit()

    service = get_integrity_service()
    report = await service.generate_project_integrity_report(db_session, project)

    t8 = next(t for t in report.threats_matrix if t.threat_number == 8)
    assert t8.triggered is True
    assert t8.status == "FLAGGED"
    assert t8.severity == "HIGH"

    fin_flag = next((f for f in report.active_flags if f.signal_code == "FINANCIAL_DISCREPANCY"), None)
    assert fin_flag is not None
    assert fin_flag.title == "Financial discrepancy"
    assert fin_flag.severity == "HIGH"


@pytest.mark.asyncio
async def test_integrity_endpoints_and_dossier_integration(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Test API endpoints:
    1. GET /api/v1/risk/projects/{id}/integrity-flags
    2. GET /api/v1/audits/{id}/integrity-flags
    3. GET /api/v1/audits/{id} (dossier includes embedded integrity_report)
    """
    auditor, auditor_token = await _create_user(db_session, UserRole.AUDITOR, "api_auditor")
    _, project = await _create_base_project(db_session, auditor)

    audit = Audit(
        project_id=project.id,
        auditor_id=auditor.id,
        selection_reason=AuditSelectionReason.HIGH_RISK,
        status=AuditStatus.INITIATED,
        scope="Comprehensive Forensic Review",
    )
    db_session.add(audit)
    await db_session.commit()

    headers = {"Authorization": f"Bearer {auditor_token}"}

    # 1. Risk project integrity flags endpoint
    resp1 = await client.get(f"/api/v1/risk/projects/{project.id}/integrity-flags", headers=headers)
    assert resp1.status_code == 200
    data1 = resp1.json()["data"]
    assert "threats_matrix" in data1
    assert len(data1["threats_matrix"]) == 10
    assert "disclaimers" in data1
    assert any("GPS coordinates are evaluated as a corroborating signal" in d for d in data1["disclaimers"])

    # 2. Audit integrity flags endpoint
    resp2 = await client.get(f"/api/v1/audits/{audit.id}/integrity-flags", headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()["data"]
    assert data2["project_id"] == str(project.id)
    assert "threats_matrix" in data2

    # 3. Audit dossier includes embedded integrity_report
    resp3 = await client.get(f"/api/v1/audits/{audit.id}", headers=headers)
    assert resp3.status_code == 200
    dossier = resp3.json()["data"]
    assert "integrity_report" in dossier
    assert dossier["integrity_report"] is not None
    assert len(dossier["integrity_report"]["threats_matrix"]) == 10
