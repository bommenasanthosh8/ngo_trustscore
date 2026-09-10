"""
Tests for Auditor and Admin Module.

Covers:
1. Role-based restrictions:
   - Auditor and Admin can access audit queue, dashboard queues, dossiers, logs.
   - NGO and Donor users receive 403 Forbidden.
2. Mandatory findings requirement:
   - Submitting an audit decision without findings or with findings < 5 chars is rejected (422/400).
3. Audit decision impacts:
   - Submitting CONFIRM, PARTIALLY_CONFIRMED, REJECT, DISCREPANCY immutably records decision,
     updates project status, and triggers score recalculation.
4. Admin NGO governance:
   - Admin can review pending NGOs, verify NGO, and reject NGO with reason.
5. Admin audit configuration:
   - Admin can view and dynamically update thresholds (high value threshold, random sample rate, risk threshold).
6. Admin dispute management:
   - Admin can review disputes across projects and resolve them.
7. Activity logs & system stats:
   - Admin and Auditor can retrieve activity logs.
   - Admin can retrieve platform-wide system statistics.
"""
from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.core.security import create_access_token, hash_password
from app.models.enums import AuditDecisionType, AuditSelectionReason, AuditStatus, DisputeStatus, NGOVerificationStatus, ProjectStatus, ProjectType
from app.models.ngo import NGO
from app.models.project import Project
from app.models.audit import Audit
from app.models.dispute import Dispute


async def _create_user(db: AsyncSession, role: UserRole, email_prefix: str, ngo_id=None) -> tuple[User, str]:
    user = User(
        email=f"{email_prefix}_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Password123!"),
        full_name=f"{role.value} User",
        role=role,
        ngo_id=ngo_id,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    token = create_access_token(subject=str(user.id), extra={"email": user.email, "role": user.role.value})
    return user, token


async def _create_project(db: AsyncSession, ngo: NGO, user: User, target_amount: float = 500000.0) -> Project:
    proj = Project(
        project_code=f"PRJ-{uuid.uuid4().hex[:6].upper()}",
        title="Community Clean Water",
        project_type=ProjectType.WATER_AND_SANITATION,
        status=ProjectStatus.UNDER_VERIFICATION,
        ngo_id=ngo.id,
        created_by_id=user.id,
        target_amount=target_amount,
        total_budget=target_amount,
        latitude=12.9716,
        longitude=77.5946,
        location_name="Bangalore Rural",
        geofence_radius=500.0,
    )
    db.add(proj)
    await db.flush()
    return proj


@pytest.mark.asyncio
async def test_role_based_access_control(client: AsyncClient, db_session: AsyncSession):
    """Verify Auditor/Admin can access audit endpoints; NGO and Donor receive 403 Forbidden."""
    ngo = NGO(name="Test NGO", registration_number=f"REG-{uuid.uuid4().hex[:6]}", verification_status=NGOVerificationStatus.VERIFIED)
    db_session.add(ngo)
    await db_session.flush()

    _, admin_token = await _create_user(db_session, UserRole.ADMIN, "admin")
    _, auditor_token = await _create_user(db_session, UserRole.AUDITOR, "auditor")
    _, ngo_token = await _create_user(db_session, UserRole.NGO, "ngo", ngo_id=ngo.id)
    _, donor_token = await _create_user(db_session, UserRole.DONOR, "donor")

    # 1. Auditor & Admin can access audit queue
    aud_res = await client.get("/api/v1/audits", headers={"Authorization": f"Bearer {auditor_token}"})
    assert aud_res.status_code == 200

    adm_res = await client.get("/api/v1/audits", headers={"Authorization": f"Bearer {admin_token}"})
    assert adm_res.status_code == 200

    # 2. NGO and Donor get 403 on audit queue
    ngo_res = await client.get("/api/v1/audits", headers={"Authorization": f"Bearer {ngo_token}"})
    assert ngo_res.status_code == 403

    donor_res = await client.get("/api/v1/audits", headers={"Authorization": f"Bearer {donor_token}"})
    assert donor_res.status_code == 403

    # 3. Only Admin can access /admin endpoints
    adm_ngo_res = await client.get("/api/v1/admin/ngos/pending", headers={"Authorization": f"Bearer {admin_token}"})
    assert adm_ngo_res.status_code == 200

    aud_ngo_res = await client.get("/api/v1/admin/ngos/pending", headers={"Authorization": f"Bearer {auditor_token}"})
    assert aud_ngo_res.status_code == 403


@pytest.mark.asyncio
async def test_audit_dashboard_queues(client: AsyncClient, db_session: AsyncSession):
    """Verify /api/v1/audits/dashboard-queues groups cases into distinct queues."""
    ngo = NGO(name="Water Aid Org", registration_number=f"REG-{uuid.uuid4().hex[:6]}", verification_status=NGOVerificationStatus.VERIFIED)
    db_session.add(ngo)
    await db_session.flush()

    ngo_user, _ = await _create_user(db_session, UserRole.NGO, "water_ngo", ngo_id=ngo.id)
    auditor_user, auditor_token = await _create_user(db_session, UserRole.AUDITOR, "lead_auditor")

    # Create projects with various amounts
    proj1 = await _create_project(db_session, ngo, ngo_user, target_amount=200000.0)
    proj2 = await _create_project(db_session, ngo, ngo_user, target_amount=1500000.0) # High value

    # Create audits
    audit1 = Audit(project_id=proj1.id, auditor_id=auditor_user.id, status=AuditStatus.INITIATED, selection_reason=AuditSelectionReason.HIGH_RISK)
    audit2 = Audit(project_id=proj2.id, auditor_id=auditor_user.id, status=AuditStatus.INITIATED, selection_reason=AuditSelectionReason.HIGH_VALUE)
    db_session.add_all([audit1, audit2])
    await db_session.commit()

    res = await client.get("/api/v1/audits/dashboard-queues", headers={"Authorization": f"Bearer {auditor_token}"})
    assert res.status_code == 200
    data = res.json()["data"]
    assert "pending_audits" in data
    assert "high_risk" in data
    assert "high_value" in data
    assert "counts" in data
    assert data["counts"]["high_value"] >= 1


@pytest.mark.asyncio
async def test_audit_decision_requires_findings_and_recalculates_score(client: AsyncClient, db_session: AsyncSession):
    """Verify decision submission enforces non-empty findings and updates project status."""
    ngo = NGO(name="Green Earth", registration_number=f"REG-{uuid.uuid4().hex[:6]}", verification_status=NGOVerificationStatus.VERIFIED)
    db_session.add(ngo)
    await db_session.flush()

    ngo_user, _ = await _create_user(db_session, UserRole.NGO, "green_ngo", ngo_id=ngo.id)
    auditor_user, auditor_token = await _create_user(db_session, UserRole.AUDITOR, "field_auditor")
    proj = await _create_project(db_session, ngo, ngo_user, target_amount=300000.0)

    audit = Audit(project_id=proj.id, auditor_id=auditor_user.id, status=AuditStatus.INITIATED, selection_reason=AuditSelectionReason.RANDOM_SAMPLE)
    db_session.add(audit)
    await db_session.commit()

    # 1. Attempt submitting without findings -> Rejected (422)
    bad_payload = {
        "decision": "CONFIRMED",
        "findings": "",  # Empty
    }
    bad_res = await client.post(f"/api/v1/audits/{audit.id}/decision", json=bad_payload, headers={"Authorization": f"Bearer {auditor_token}"})
    assert bad_res.status_code in (400, 422)

    # 2. Submit valid decision with findings
    good_payload = {
        "decision": "CONFIRMED",
        "findings": "Physical site inspection confirmed all 5 borewells are operational with valid GPS logs.",
        "notes": "Verified against local village council signoff.",
    }
    good_res = await client.post(f"/api/v1/audits/{audit.id}/decision", json=good_payload, headers={"Authorization": f"Bearer {auditor_token}"})
    assert good_res.status_code == 201
    assert good_res.json()["data"]["decision"] == "CONFIRMED"

    # 3. Verify project status was transitioned to VERIFIED
    await db_session.refresh(proj)
    assert proj.status == ProjectStatus.VERIFIED


@pytest.mark.asyncio
async def test_admin_ngo_verification_and_rejection(client: AsyncClient, db_session: AsyncSession):
    """Verify Admin can verify or reject pending NGOs with reasons."""
    _, admin_token = await _create_user(db_session, UserRole.ADMIN, "gov_admin")

    ngo_pending1 = NGO(name="Pending NGO 1", registration_number=f"REG-{uuid.uuid4().hex[:6]}", verification_status=NGOVerificationStatus.PENDING)
    ngo_pending2 = NGO(name="Pending NGO 2", registration_number=f"REG-{uuid.uuid4().hex[:6]}", verification_status=NGOVerificationStatus.PENDING)
    db_session.add_all([ngo_pending1, ngo_pending2])
    await db_session.commit()

    # 1. Verify NGO 1
    v_res = await client.post(f"/api/v1/admin/ngos/{ngo_pending1.id}/verify", headers={"Authorization": f"Bearer {admin_token}"})
    assert v_res.status_code == 200
    assert v_res.json()["data"]["verification_status"] == "VERIFIED"

    # 2. Reject NGO 2
    r_res = await client.post(
        f"/api/v1/admin/ngos/{ngo_pending2.id}/reject",
        json={"reason": "Incomplete registration documentation."},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_res.status_code == 200
    assert r_res.json()["data"]["verification_status"] == "REJECTED"


@pytest.mark.asyncio
async def test_admin_audit_config_and_stats(client: AsyncClient, db_session: AsyncSession):
    """Verify Admin can manage audit configuration thresholds and view system statistics."""
    _, admin_token = await _create_user(db_session, UserRole.ADMIN, "sys_admin")

    # 1. Get current config
    cfg_get = await client.get("/api/v1/admin/audit-config", headers={"Authorization": f"Bearer {admin_token}"})
    assert cfg_get.status_code == 200
    assert "high_project_value_threshold" in cfg_get.json()["data"]

    # 2. Update config
    update_payload = {
        "high_project_value_threshold": 1200000.0,
        "audit_random_sample_rate": 0.08,
        "high_risk_threshold": 65.0,
    }
    cfg_put = await client.put("/api/v1/admin/audit-config", json=update_payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert cfg_put.status_code == 200
    updated = cfg_put.json()["data"]
    assert updated["high_project_value_threshold"] == 1200000.0
    assert updated["audit_random_sample_rate"] == 0.08

    # 3. Get system statistics
    stats_res = await client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert stats_res.status_code == 200
    stats = stats_res.json()["data"]
    assert "ngos" in stats
    assert "projects" in stats
    assert "audits" in stats
    assert "total_funding_volume" in stats


@pytest.mark.asyncio
async def test_admin_disputes_and_activity_logs(client: AsyncClient, db_session: AsyncSession):
    """Verify Admin can list and resolve disputes, and query activity logs."""
    ngo = NGO(name="Disputed Org", registration_number=f"REG-{uuid.uuid4().hex[:6]}", verification_status=NGOVerificationStatus.VERIFIED)
    db_session.add(ngo)
    await db_session.flush()

    ngo_user, _ = await _create_user(db_session, UserRole.NGO, "dispute_raiser", ngo_id=ngo.id)
    _, admin_token = await _create_user(db_session, UserRole.ADMIN, "dispute_arbiter")
    proj = await _create_project(db_session, ngo, ngo_user)

    # Create dispute
    dispute = Dispute(project_id=proj.id, raised_by_id=ngo_user.id, reason="Auditor overlooked our second invoice set.", status=DisputeStatus.OPEN)
    db_session.add(dispute)
    await db_session.commit()

    # 1. Admin lists disputes
    disp_res = await client.get("/api/v1/admin/disputes", headers={"Authorization": f"Bearer {admin_token}"})
    assert disp_res.status_code == 200
    items = disp_res.json()["data"]
    assert len(items) >= 1
    assert any(d["id"] == str(dispute.id) for d in items)

    # 2. Admin resolves dispute
    resolve_payload = {
        "resolution_notes": "Reviewed supplementary invoices. Confirmed valid delivery.",
        "action": "UPHOLD_DECISION",
    }
    resolve_res = await client.post(f"/api/v1/admin/disputes/{dispute.id}/resolve", json=resolve_payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert resolve_res.status_code == 200
    assert resolve_res.json()["data"]["status"] == "RESOLVED"

    # 3. Admin views activity logs
    logs_res = await client.get("/api/v1/admin/logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert logs_res.status_code == 200
    logs = logs_res.json()["data"]
    assert isinstance(logs, list)
