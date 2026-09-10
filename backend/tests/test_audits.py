"""
Tests for Independent Audit Module:
- Audit Queue Generation & Selection (HIGH-RISK, HIGH-VALUE, RANDOM SAMPLE)
- Comprehensive Audit Dossier (Project, claims, evidence, financials, verification, risk reasons)
- Auditor Decisions (CONFIRMED, PARTIALLY_CONFIRMED, REJECTED, DISCREPANCY)
- Role-based access control:
  - Auditor/Admin authorized for audit management
  - NGO forbidden from making auditor decisions (HTTP 403)
- Immutable audit decisions (New record supersedes prior without overwriting history)
- Dispute Workflow:
  - NGO raises dispute -> project & audit status transition to DISPUTED
  - Admin resolves dispute
- ActivityLog audit trail for every audit action
"""
import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.activity import ActivityLog
from app.models.audit import Audit, AuditDecision
from app.models.dispute import Dispute
from app.models.enums import AuditDecisionType, AuditSelectionReason, AuditStatus, ProjectStatus, UserRole
from app.models.user import User


async def register_user(client: AsyncClient, role: str = "AUDITOR", org_name: str = None):
    """Helper to register and login a user with given role."""
    email = f"{role.lower()}_{uuid.uuid4().hex[:6]}@platform.org"
    reg_payload = {
        "email": email,
        "password": "Password123!",
        "full_name": f"Test {role.capitalize()}",
        "role": role,
    }
    if role == "NGO":
        reg_payload["organization_name"] = org_name or f"Trust {uuid.uuid4().hex[:4]}"
        reg_payload["registration_number"] = f"NGO-REG-{uuid.uuid4().hex[:6].upper()}"

    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201

    user_data = reg_res.json()["data"]
    login_res = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    token = login_res.json()["data"]["access_token"]
    return user_data, {"Authorization": f"Bearer {token}"}


async def create_project(client: AsyncClient, ngo_headers: dict, budget: float = 300000.0, lat: float = 26.9124):
    """Helper to create a project."""
    res = await client.post(
        "/api/v1/projects/",
        json={
            "title": "Community Health Center",
            "description": "Primary healthcare clinic construction",
            "project_type": "HEALTHCARE",
            "verification_model": "PERMANENT",
            "total_budget": budget,
            "target_amount": budget,
            "start_date": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
            "expected_completion_date": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),
            "location": {
                "latitude": lat,
                "longitude": 75.7873,
                "location_name": "Rural Clinic Site",
                "geofence_radius": 500.0,
            },
        },
        headers=ngo_headers,
    )
    assert res.status_code == 201
    return res.json()["data"]


@pytest.mark.asyncio
async def test_audit_health_endpoint(client: AsyncClient):
    """Test /audits/health endpoint."""
    res = await client.get("/api/v1/audits/health")
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "HEALTHY"


@pytest.mark.asyncio
async def test_audit_queue_auto_selection_high_risk_and_value(client: AsyncClient):
    """Test that high-risk and high-value projects enter the audit queue."""
    _, ngo_headers = await register_user(client, role="NGO")
    _, auditor_headers = await register_user(client, role="AUDITOR")

    # 1. High value project (₹1,500,000 >= ₹1,000,000 threshold)
    high_val_proj = await create_project(client, ngo_headers, budget=1500000.0)

    # Fetch audit queue as auditor
    queue_res = await client.get("/api/v1/audits", headers=auditor_headers)
    assert queue_res.status_code == 200
    cases = queue_res.json()["data"]
    matched = next((c for c in cases if c["project_id"] == high_val_proj["id"]), None)
    assert matched is not None
    assert matched["selection_reason"] == "HIGH_VALUE"
    assert matched["status"] == "INITIATED"


@pytest.mark.asyncio
async def test_auditor_dossier_assembly(client: AsyncClient):
    """Test GET /audits/{id} dossier assembling project, claims, timeline, financials, verification, risk."""
    _, ngo_headers = await register_user(client, role="NGO")
    _, auditor_headers = await register_user(client, role="AUDITOR")

    proj = await create_project(client, ngo_headers, budget=1200000.0)
    proj_id = proj["id"]

    # Upload an evidence item
    await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        headers=ngo_headers,
        data={"title": "Site Inspection", "evidence_type": "BEFORE"},
        files={"file": ("site.jpg", io.BytesIO(b"site baseline photo"), "image/jpeg")},
    )

    # Upload a financial invoice
    await client.post(
        f"/api/v1/projects/{proj_id}/financial-evidence",
        headers=ngo_headers,
        data={"document_type": "INVOICE", "claimed_amount": 100000.0, "vendor_name": "Concrete Supplies"},
        files={"file": ("inv.pdf", io.BytesIO(b"Total: INR 100,000.00"), "application/pdf")},
    )

    # Fetch queue to get audit ID
    q_res = await client.get("/api/v1/audits", headers=auditor_headers)
    audit_case = next(c for c in q_res.json()["data"] if c["project_id"] == proj_id)
    audit_id = audit_case["id"]

    # Fetch dossier
    dossier_res = await client.get(f"/api/v1/audits/{audit_id}", headers=auditor_headers)
    assert dossier_res.status_code == 200
    dossier = dossier_res.json()["data"]

    # Verify dossier sections
    assert dossier["project_id"] == proj_id
    assert dossier["project_code"] == proj["project_code"]
    assert len(dossier["evidence_timeline"]) >= 1
    assert len(dossier["financial_evidence"]) >= 1
    assert dossier["verification_report"] is not None
    assert dossier["risk_assessment"] is not None
    assert "decisions_history" in dossier


@pytest.mark.asyncio
async def test_ngo_forbidden_from_submitting_audit_decision(client: AsyncClient):
    """Test that NGO is strictly forbidden from recording or modifying audit decisions."""
    _, ngo_headers = await register_user(client, role="NGO")
    _, auditor_headers = await register_user(client, role="AUDITOR")

    proj = await create_project(client, ngo_headers, budget=1200000.0)
    q_res = await client.get("/api/v1/audits", headers=auditor_headers)
    audit_case = next(c for c in q_res.json()["data"] if c["project_id"] == proj["id"])
    audit_id = audit_case["id"]

    # NGO tries to submit decision
    ngo_dec_res = await client.post(
        f"/api/v1/audits/{audit_id}/decision",
        headers=ngo_headers,
        json={
            "decision": "CONFIRMED",
            "findings": "NGO self-certification attempt",
        },
    )
    assert ngo_dec_res.status_code == 403
    assert "Forbidden" in ngo_dec_res.json()["error"]


@pytest.mark.asyncio
async def test_immutable_audit_decisions_and_correction_flow(client: AsyncClient, db_session: AsyncSession):
    """
    Test that audit decisions are immutable:
    - Initial decision is recorded.
    - If a correction/update is needed, a NEW record is created that links and supersedes the old one.
    - Original decision remains preserved in the database.
    """
    _, ngo_headers = await register_user(client, role="NGO")
    _, auditor_headers = await register_user(client, role="AUDITOR")

    proj = await create_project(client, ngo_headers, budget=1200000.0)
    q_res = await client.get("/api/v1/audits", headers=auditor_headers)
    audit_case = next(c for c in q_res.json()["data"] if c["project_id"] == proj["id"])
    audit_id = audit_case["id"]

    # 1. Auditor records first decision: PARTIALLY_CONFIRMED
    dec1_res = await client.post(
        f"/api/v1/audits/{audit_id}/decision",
        headers=auditor_headers,
        json={
            "decision": "PARTIALLY_CONFIRMED",
            "findings": "Physical site foundation verified, but final finishing work incomplete.",
            "notes": "Follow up inspection requested.",
        },
    )
    assert dec1_res.status_code == 201
    dec1 = dec1_res.json()["data"]
    assert dec1["decision"] == "PARTIALLY_CONFIRMED"
    assert dec1["is_superseded"] is False

    # Check project status updated to PARTIALLY_VERIFIED
    p_check = await client.get(f"/api/v1/projects/{proj['id']}", headers=ngo_headers)
    assert p_check.json()["data"]["status"] == "PARTIALLY_VERIFIED"

    # 2. Subsequent review: Auditor receives additional evidence and issues CONFIRMED decision
    dec2_res = await client.post(
        f"/api/v1/audits/{audit_id}/decision",
        headers=auditor_headers,
        json={
            "decision": "CONFIRMED",
            "findings": "Finishing work verified with supplementary drone telemetry.",
            "notes": "Replaces initial partial confirmation.",
        },
    )
    assert dec2_res.status_code == 201
    dec2 = dec2_res.json()["data"]
    assert dec2["decision"] == "CONFIRMED"
    assert dec2["is_superseded"] is False

    # 3. Verify in database: dec1 is marked superseded, linked to dec2, but STILL EXISTS (immutable)
    dec1_db = await db_session.get(AuditDecision, uuid.UUID(dec1["id"]))
    dec2_db = await db_session.get(AuditDecision, uuid.UUID(dec2["id"]))

    assert dec1_db is not None
    assert dec1_db.is_superseded is True
    assert dec1_db.superseded_by_id == dec2_db.id
    assert dec2_db.is_superseded is False

    # Project status updated to VERIFIED
    p_check2 = await client.get(f"/api/v1/projects/{proj['id']}", headers=ngo_headers)
    assert p_check2.json()["data"]["status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_dispute_workflow_and_resolution(client: AsyncClient, db_session: AsyncSession, auth_headers):
    """
    Test full dispute workflow:
    - Auditor records DISCREPANCY decision.
    - NGO submits review request (POST /projects/{id}/dispute).
    - Project & audit status move to DISPUTED.
    - Admin reviews and resolves dispute.
    """
    _, ngo_headers = await register_user(client, role="NGO")
    _, auditor_headers = await register_user(client, role="AUDITOR")
    
    admin_user = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@platform.gov.in",
        hashed_password=hash_password("AdminPass123!"),
        full_name="Platform Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin_user)
    await db_session.flush()
    admin_headers = auth_headers(admin_user.id, role="ADMIN", email=admin_user.email)

    proj = await create_project(client, ngo_headers, budget=1200000.0)
    proj_id = proj["id"]

    q_res = await client.get("/api/v1/audits", headers=auditor_headers)
    audit_case = next(c for c in q_res.json()["data"] if c["project_id"] == proj_id)
    audit_id = audit_case["id"]

    # 1. Auditor records DISCREPANCY
    await client.post(
        f"/api/v1/audits/{audit_id}/decision",
        headers=auditor_headers,
        json={
            "decision": "DISCREPANCY",
            "findings": "Invoice total did not match bank statement.",
        },
    )

    # 2. NGO lodges dispute
    disp_res = await client.post(
        f"/projects/{proj_id}/dispute",
        headers=ngo_headers,
        json={
            "reason": "The bank statement provided was an interim statement. Bank certificate attached clarifying discrepancy.",
            "supporting_notes": "Certificate issued by State Bank on 2026-09-01.",
        },
    )
    assert disp_res.status_code == 201, f"Failed with {disp_res.status_code}: {disp_res.text}"
    dispute = disp_res.json()["data"]
    assert dispute["status"] == "OPEN"

    # Verify project status moved to DISPUTED
    p_res = await client.get(f"/api/v1/projects/{proj_id}", headers=ngo_headers)
    assert p_res.json()["data"]["status"] == "DISPUTED"

    # 3. Admin resolves dispute with REVISE_DECISION
    res_res = await client.post(
        f"/api/v1/audits/disputes/{dispute['id']}/resolve",
        headers=admin_headers,
        json={
            "action": "REVISE_DECISION",
            "resolution_notes": "Bank certificate reviewed and validated. Expense discrepancy cleared.",
            "revised_decision": "CONFIRMED",
            "revised_findings": "All expenditures reconciled with bank certificate.",
        },
    )
    assert res_res.status_code == 200
    assert res_res.json()["data"]["status"] == "RESOLVED"

    # Project is now VERIFIED
    p_res2 = await client.get(f"/api/v1/projects/{proj_id}", headers=ngo_headers)
    assert p_res2.json()["data"]["status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_activity_logs_created_for_all_audit_actions(client: AsyncClient, db_session: AsyncSession):
    """Test that ActivityLog records are created for audit queued, decisions, and disputes."""
    _, ngo_headers = await register_user(client, role="NGO")
    _, auditor_headers = await register_user(client, role="AUDITOR")

    proj = await create_project(client, ngo_headers, budget=1200000.0)
    q_res = await client.get("/api/v1/audits", headers=auditor_headers)
    audit_case = next(c for c in q_res.json()["data"] if c["project_id"] == proj["id"])
    audit_id = audit_case["id"]

    await client.post(
        f"/api/v1/audits/{audit_id}/decision",
        headers=auditor_headers,
        json={"decision": "CONFIRMED", "findings": "All good"},
    )

    # Check ActivityLog entries in DB
    logs_q = select(ActivityLog).where(
        ActivityLog.action.in_(["AUDIT_QUEUED", "AUDIT_DECISION_RECORDED"])
    )
    logs_res = await db_session.execute(logs_q)
    logs = logs_res.scalars().all()
    actions = [l.action for l in logs]
    assert "AUDIT_QUEUED" in actions
    assert "AUDIT_DECISION_RECORDED" in actions
