"""
Tests for Project Evidence Score Engine:
- Authoritative 100-point composite scoring across 6 evidence factors
- Score Status classification (STRONG_EVIDENCE, GOOD_EVIDENCE, LIMITED_EVIDENCE, WEAK_EVIDENCE)
- Factor breakdown (earned points, maximum points, explanations, source verification results)
- Backend authoritative guarantee (frontend cannot submit scores)
- Active dispute status display and audit factor adjustment
- Database persistence of ScoreSnapshot and ActivityLog emission
"""
import io
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.activity import ActivityLog
from app.models.enums import ScoreStatus, UserRole
from app.models.score import ScoreSnapshot
from app.models.user import User


async def register_user(client: AsyncClient, role: str = "NGO", org_name: str = None):
    """Helper to register and login a user with given role."""
    email = f"{role.lower()}_{uuid.uuid4().hex[:6]}@platform.org"
    reg_payload = {
        "email": email,
        "password": "Password123!",
        "full_name": f"Test {role.capitalize()}",
        "role": role,
    }
    if role == "NGO":
        reg_payload["organization_name"] = org_name or f"Score Trust {uuid.uuid4().hex[:4]}"
        reg_payload["registration_number"] = f"NGO-SCORE-{uuid.uuid4().hex[:6].upper()}"

    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["data"]["access_token"]
    return email, {"Authorization": f"Bearer {token}"}


async def create_test_project(client: AsyncClient, ngo_headers: dict, **kwargs) -> dict:
    """Helper to create a project with geographic location."""
    default_payload = {
        "name": kwargs.get("name", "Solar Water Pump Station"),
        "category": kwargs.get("category", "WATER_AND_SANITATION"),
        "description": "Comprehensive solar-powered deep borewell water distribution facility.",
        "target_amount": kwargs.get("budget", 600000.0),
        "expected_beneficiaries": 1200,
        "expected_outcome": "Clean drinking water for 1,200 rural households.",
        "location": {
            "latitude": 13.0827,
            "longitude": 80.2707,
            "geofence_radius": 500.0,
            "location_name": "Villupuram Rural Site",
        },
    }
    default_payload.update(kwargs)
    res = await client.post("/api/v1/projects/", json=default_payload, headers=ngo_headers)
    assert res.status_code == 201
    return res.json()["data"]


@pytest.mark.asyncio
async def test_score_health_endpoint(client: AsyncClient):
    """Test GET /scores/health endpoint."""
    res = await client.get("/scores/health")
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["data"]["status"] == "HEALTHY"


@pytest.mark.asyncio
async def test_strong_evidence_project_score(client: AsyncClient):
    """
    Test complete lifecycle yielding STRONG_EVIDENCE:
    - Complete project identity
    - Location within 40m of registered site
    - Full timeline (BEFORE, PROGRESS, COMPLETION)
    - Valid financial invoice matching expenditure
    - Independent audit CONFIRMED
    """
    _, ngo_headers = await register_user(client, role="NGO")
    _, auditor_headers = await register_user(client, role="AUDITOR")

    project = await create_test_project(client, ngo_headers, budget=1200000.0)
    proj_id = project["id"]

    # 1. Upload BEFORE evidence (within 30m)
    await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        headers=ngo_headers,
        data={
            "title": "Site Baseline Survey",
            "evidence_type": "BEFORE",
            "latitude": 13.0829,  # ~25m from 13.0827
            "longitude": 80.2708,
        },
        files={"file": ("before.jpg", io.BytesIO(b"original land site photo"), "image/jpeg")},
    )

    # 2. Upload PROGRESS evidence
    await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        headers=ngo_headers,
        data={
            "title": "Excavation and Drilling",
            "evidence_type": "PROGRESS",
            "latitude": 13.0828,
            "longitude": 80.2707,
        },
        files={"file": ("progress.jpg", io.BytesIO(b"excavation photo progress"), "image/jpeg")},
    )

    # 3. Upload COMPLETION evidence
    await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        headers=ngo_headers,
        data={
            "title": "Commissioned Water Station",
            "evidence_type": "COMPLETION",
            "latitude": 13.0827,
            "longitude": 80.2707,
        },
        files={"file": ("completion.jpg", io.BytesIO(b"finished station water tap"), "image/jpeg")},
    )

    # 4. Upload financial invoice fully supporting expenditure
    await client.post(
        f"/api/v1/projects/{proj_id}/financial-evidence",
        headers=ngo_headers,
        data={
            "document_type": "INVOICE",
            "claimed_amount": 1200000.0,
            "vendor_name": "Apex Solar Ltd",
        },
        files={"file": ("invoice.pdf", io.BytesIO(b"Apex Solar Ltd Total: INR 1,200,000.00"), "application/pdf")},
    )

    # 5. Auditor records CONFIRMED decision
    q_res = await client.get("/api/v1/audits", headers=auditor_headers)
    assert q_res.status_code == 200
    cases = q_res.json()["data"]
    audit_case = next((c for c in cases if c["project_id"] == proj_id), None)
    if not audit_case:
        # If not queued by high value, auditor can fetch dossier
        pass
    else:
        await client.post(
            f"/api/v1/audits/{audit_case['id']}/decision",
            headers=auditor_headers,
            json={
                "decision": "CONFIRMED",
                "findings": "Physical site inspection confirmed operational borewell.",
            },
        )

    # 6. Fetch project score via GET /projects/{id}/score
    score_res = await client.get(f"/projects/{proj_id}/score", headers=ngo_headers)
    assert score_res.status_code == 200
    score_data = score_res.json()["data"]

    # Verify score attributes
    assert score_data["project_id"] == proj_id
    assert score_data["final_score"] >= 80.0
    assert score_data["status"] == ScoreStatus.STRONG_EVIDENCE.value
    assert score_data["is_disputed"] is False

    # Verify 6 factor breakdown
    factors = score_data["factors"]
    assert "location_consistency" in factors
    assert "timeline_timestamp" in factors
    assert "media_evidence" in factors
    assert "financial_evidence" in factors
    assert "project_identity" in factors
    assert "independent_audit" in factors

    # Check Location Factor
    loc = factors["location_consistency"]
    assert loc["maximum_points"] == 20.0
    assert loc["earned_points"] >= 18.0
    assert "Evidence captured within" in loc["explanation"]

    # Check Timeline Factor
    tl = factors["timeline_timestamp"]
    assert tl["maximum_points"] == 15.0
    assert tl["earned_points"] >= 14.0
    assert "Before, progress and completion" in tl["explanation"]

    # Check Media Factor
    media = factors["media_evidence"]
    assert media["maximum_points"] == 20.0
    assert media["earned_points"] >= 17.0
    assert "visual evidence is consistent" in media["explanation"]

    # Check Financial Factor
    fin = factors["financial_evidence"]
    assert fin["maximum_points"] == 20.0
    assert fin["earned_points"] >= 16.0

    # Check Project Identity Factor
    ident = factors["project_identity"]
    assert ident["maximum_points"] == 10.0
    assert ident["earned_points"] >= 8.0


@pytest.mark.asyncio
async def test_weak_and_limited_evidence_project(client: AsyncClient):
    """
    Test scenario where project lacks evidence and financials, yielding WEAK_EVIDENCE:
    - Zero financial documents
    - No GPS coordinates
    - Single unclassified evidence file
    """
    _, ngo_headers = await register_user(client, role="NGO")

    project = await create_test_project(client, ngo_headers, budget=200000.0)
    proj_id = project["id"]

    # No evidence uploaded at all
    score_res = await client.get(f"/projects/{proj_id}/score", headers=ngo_headers)
    assert score_res.status_code == 200
    score_data = score_res.json()["data"]

    # Final score should be low (< 45) -> WEAK_EVIDENCE
    assert score_data["final_score"] < 45.0
    assert score_data["status"] == ScoreStatus.WEAK_EVIDENCE.value

    factors = score_data["factors"]
    assert factors["location_consistency"]["earned_points"] == 0.0
    assert factors["timeline_timestamp"]["earned_points"] == 0.0
    assert factors["financial_evidence"]["earned_points"] == 0.0
    assert "Areas needing attention" in score_data["explanation"]


@pytest.mark.asyncio
async def test_disputed_project_score_flagging(client: AsyncClient, db_session: AsyncSession, auth_headers):
    """
    Test that disputed projects clearly display their dispute status in GET /projects/{id}/score:
    - Auditor records DISCREPANCY
    - NGO lodges dispute
    - Score reflects is_disputed=True, dispute_status='OPEN', and [DISPUTED] narrative warning
    """
    _, ngo_headers = await register_user(client, role="NGO")
    _, auditor_headers = await register_user(client, role="AUDITOR")

    project = await create_test_project(client, ngo_headers, budget=1500000.0)
    proj_id = project["id"]

    # Fetch audit case
    q_res = await client.get("/api/v1/audits", headers=auditor_headers)
    audit_case = next(c for c in q_res.json()["data"] if c["project_id"] == proj_id)

    # 1. Auditor records DISCREPANCY
    await client.post(
        f"/api/v1/audits/{audit_case['id']}/decision",
        headers=auditor_headers,
        json={"decision": "DISCREPANCY", "findings": "Discrepancy in supplier payment vouchers."},
    )

    # 2. NGO disputes decision
    disp_res = await client.post(
        f"/projects/{proj_id}/dispute",
        headers=ngo_headers,
        json={
            "reason": "Vouchers were misfiled under subcontractor account. Correct ledger attached.",
            "supporting_notes": "Subcontractor reconciliation statement attached.",
        },
    )
    assert disp_res.status_code == 201

    # 3. Query score
    score_res = await client.get(f"/projects/{proj_id}/score", headers=ngo_headers)
    assert score_res.status_code == 200
    score = score_res.json()["data"]

    assert score["is_disputed"] is True
    assert score["dispute_status"] == "OPEN"
    assert "[DISPUTED]" in score["explanation"]
    assert "[DISPUTED]" in score["factors"]["independent_audit"]["explanation"]


@pytest.mark.asyncio
async def test_frontend_cannot_submit_score(client: AsyncClient):
    """
    Test security guarantee: The backend is strictly authoritative.
    Frontend cannot POST or PUT an arbitrary score to the project.
    """
    _, ngo_headers = await register_user(client, role="NGO")
    project = await create_test_project(client, ngo_headers)
    proj_id = project["id"]

    # Attempt POST to /projects/{id}/score
    post_res = await client.post(
        f"/projects/{proj_id}/score",
        json={"final_score": 99.0, "status": "STRONG_EVIDENCE"},
        headers=ngo_headers,
    )
    assert post_res.status_code == 405  # Method Not Allowed

    # Attempt PUT to /projects/{id}/score
    put_res = await client.put(
        f"/projects/{proj_id}/score",
        json={"final_score": 99.0},
        headers=ngo_headers,
    )
    assert put_res.status_code == 405  # Method Not Allowed


@pytest.mark.asyncio
async def test_score_snapshot_and_activity_log_persisted(client: AsyncClient, db_session: AsyncSession):
    """Test that calculating a score persists ScoreSnapshot and logs ActivityLog in the database."""
    _, ngo_headers = await register_user(client, role="NGO")
    project = await create_test_project(client, ngo_headers, budget=500000.0)
    proj_id = project["id"]

    # Query score to trigger calculation & snapshot
    res = await client.get(f"/projects/{proj_id}/score", headers=ngo_headers)
    assert res.status_code == 200

    # Verify ScoreSnapshot in database
    snap_q = select(ScoreSnapshot).where(ScoreSnapshot.project_id == uuid.UUID(proj_id))
    snap_res = await db_session.execute(snap_q)
    snapshots = snap_res.scalars().all()
    assert len(snapshots) >= 1
    latest_snap = snapshots[-1]
    assert float(latest_snap.composite_score) >= 0.0
    assert "factors" in latest_snap.breakdown

    # Verify ActivityLog in database
    log_q = select(ActivityLog).where(
        ActivityLog.resource_id == str(proj_id),
        ActivityLog.action == "SCORE_CALCULATED",
    )
    log_res = await db_session.execute(log_q)
    logs = log_res.scalars().all()
    assert len(logs) >= 1
    assert logs[0].action == "SCORE_CALCULATED"
