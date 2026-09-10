"""
Comprehensive tests for the Risk Assessment Engine:
- 10 multi-factor risk signals:
  1. Location mismatch
  2. Missing timeline evidence
  3. Duplicate media
  4. Suspicious metadata
  5. Financial inconsistency
  6. Repeated failed submissions
  7. High project value
  8. Previous disputes
  9. Unusual evidence patterns
  10. Incomplete evidence
- Clamped risk scores (0–100)
- Risk levels: LOW (0–29), MEDIUM (30–59), HIGH (60–100)
- Narrative explanations per risk factor
- Audit triggers: HIGH_RISK_SCORE, HIGH_PROJECT_VALUE, RANDOM_SAMPLE_SELECTION
- Endpoints: GET /projects/{id}/risk, GET /api/v1/projects/{id}/risk
"""
import hashlib
import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dispute import Dispute
from app.models.enums import DisputeStatus


async def setup_test_project(
    client: AsyncClient,
    title: str = "Solar Water Purification Plant",
    category: str = "WATER_AND_SANITATION",
    model: str = "PERMANENT",
    budget: float = 300000.0,
    lat: float = 26.9124,
    lng: float = 75.7873,
    radius: float = 500.0,
):
    """Register an NGO and create a project."""
    email = f"risk_lead_{uuid.uuid4().hex[:6]}@cleantrust.org"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Deepak Verma",
            "role": "NGO",
            "organization_name": f"Clean Water Trust {uuid.uuid4().hex[:4]}",
            "registration_number": f"NGO-RISK-{uuid.uuid4().hex[:6].upper()}",
        },
    )
    assert reg_res.status_code == 201

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    start_date = datetime.now(timezone.utc) - timedelta(days=20)
    end_date = datetime.now(timezone.utc) + timedelta(days=90)

    proj_res = await client.post(
        "/api/v1/projects/",
        json={
            "title": title,
            "description": "Safe drinking water for 500 households",
            "project_type": category,
            "verification_model": model,
            "total_budget": budget,
            "target_amount": budget,
            "start_date": start_date.isoformat(),
            "expected_completion_date": end_date.isoformat(),
            "location": {
                "latitude": lat,
                "longitude": lng,
                "location_name": "Chomu Rural Water Station",
                "geofence_radius": radius,
            },
        },
        headers=headers,
    )
    assert proj_res.status_code == 201
    return proj_res.json()["data"], headers


@pytest.mark.asyncio
async def test_risk_health_endpoint(client: AsyncClient):
    """Test /risk/health endpoint returns weights and thresholds."""
    res = await client.get("/api/v1/risk/health")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["status"] == "HEALTHY"
    assert data["weights"]["location_mismatch"] == 25.0
    assert data["weights"]["financial_discrepancy"] == 25.0
    assert data["weights"]["duplicate_media"] == 20.0
    assert data["thresholds"]["high_project_value_threshold"] == 1000000.0


@pytest.mark.asyncio
async def test_low_risk_project(client: AsyncClient):
    """A clean, compliant project should have LOW risk (score < 30) with no audit recommended."""
    proj, headers = await setup_test_project(client, budget=400000.0)
    proj_id = proj["id"]

    # Upload BEFORE evidence at exact location
    await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        headers=headers,
        data={
            "title": "Baseline Site Survey",
            "evidence_type": "BEFORE",
            "latitude": 26.9124,
            "longitude": 75.7873,
            "metadata_summary": '{"make": "Sony", "model": "A7"}',
        },
        files={"file": ("survey.jpg", io.BytesIO(b"baseline unique survey photo"), "image/jpeg")},
    )

    # Upload PROGRESS
    await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        headers=headers,
        data={
            "title": "Foundation Work",
            "evidence_type": "PROGRESS",
            "latitude": 26.9125,
            "longitude": 75.7874,
            "metadata_summary": '{"make": "Sony", "model": "A7"}',
        },
        files={"file": ("progress.jpg", io.BytesIO(b"foundation unique work photo"), "image/jpeg")},
    )

    # Upload COMPLETION
    await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        headers=headers,
        data={
            "title": "Final Filtration Plant",
            "evidence_type": "COMPLETION",
            "latitude": 26.9124,
            "longitude": 75.7873,
            "metadata_summary": '{"make": "Sony", "model": "A7"}',
        },
        files={"file": ("completed.jpg", io.BytesIO(b"completed unique plant photo"), "image/jpeg")},
    )

    # Upload matching financial bill
    await client.post(
        f"/api/v1/projects/{proj_id}/financial-evidence",
        headers=headers,
        data={
            "document_type": "BILL",
            "claimed_amount": 395000.0,
            "vendor_name": "Apex Water Works",
        },
        files={"file": ("bill.pdf", io.BytesIO(b"Grand Total: INR 395,000.00"), "application/pdf")},
    )

    # Evaluate risk
    risk_res = await client.get(f"/api/v1/projects/{proj_id}/risk", headers=headers)
    assert risk_res.status_code == 200
    report = risk_res.json()["data"]

    assert report["risk_level"] == "LOW"
    assert report["risk_score"] < 30.0
    assert report["audit_trigger"]["audit_recommended"] is False


@pytest.mark.asyncio
async def test_location_mismatch_signal(client: AsyncClient):
    """Test Location mismatch risk signal (+25) and narrative explanation."""
    proj, headers = await setup_test_project(client, lat=26.9124, lng=75.7873, radius=500.0)
    proj_id = proj["id"]

    # Upload evidence 14 km away (approx 0.13 degrees latitude shift)
    await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        headers=headers,
        data={
            "title": "Distant Borewell",
            "evidence_type": "COMPLETION",
            "latitude": 27.0400,  # ~14 km north
            "longitude": 75.7873,
        },
        files={"file": ("borewell.jpg", io.BytesIO(b"distant well photo"), "image/jpeg")},
    )

    risk_res = await client.get(f"/projects/{proj_id}/risk", headers=headers)
    assert risk_res.status_code == 200
    report = risk_res.json()["data"]

    loc_sig = next(s for s in report["signals"] if s["signal_name"] == "Location Mismatch")
    assert loc_sig["triggered"] is True
    assert loc_sig["score_contribution"] == 25.0
    assert "Evidence captured" in loc_sig["explanation"]
    assert "km from registered project location" in loc_sig["explanation"]
    assert any("Evidence captured" in r for r in report["reasons"])


@pytest.mark.asyncio
async def test_financial_discrepancy_signal(client: AsyncClient):
    """Test Financial Inconsistency signal (+25) when documents support only part of claimed expenditure."""
    proj, headers = await setup_test_project(client, budget=500000.0)
    proj_id = proj["id"]

    # Claim ₹500,000, but document only extracts ₹250,000 (50% support)
    await client.post(
        f"/api/v1/projects/{proj_id}/financial-evidence",
        headers=headers,
        data={
            "document_type": "INVOICE",
            "claimed_amount": 500000.0,
            "vendor_name": "Subcontractor Ltd",
        },
        files={"file": ("invoice.pdf", io.BytesIO(b"Total: INR 250,000.00"), "application/pdf")},
    )

    risk_res = await client.get(f"/projects/{proj_id}/risk", headers=headers)
    assert risk_res.status_code == 200
    report = risk_res.json()["data"]

    fin_sig = next(s for s in report["signals"] if s["signal_name"] == "Financial Inconsistency")
    assert fin_sig["triggered"] is True
    assert fin_sig["score_contribution"] == 25.0
    assert "Financial documents support only" in fin_sig["explanation"]
    assert any("Financial documents support only" in r for r in report["reasons"])


@pytest.mark.asyncio
async def test_duplicate_media_cross_project(client: AsyncClient):
    """Test Duplicate Media signal (+20) when image hash is shared across projects."""
    p1, h1 = await setup_test_project(client, title="Project Alpha")
    p2, h2 = await setup_test_project(client, title="Project Beta")

    shared_media = b"SHARED_RECYCLED_PICTURE_BETWEEN_TWO_PROJECTS_XYZ"

    # Upload to Project 1
    await client.post(
        f"/api/v1/projects/{p1['id']}/evidence",
        headers=h1,
        data={"title": "Plant Photo", "evidence_type": "BEFORE"},
        files={"file": ("p1.jpg", io.BytesIO(shared_media), "image/jpeg")},
    )

    # Upload to Project 2
    await client.post(
        f"/api/v1/projects/{p2['id']}/evidence",
        headers=h2,
        data={"title": "Duplicate Photo", "evidence_type": "BEFORE"},
        files={"file": ("p2.jpg", io.BytesIO(shared_media), "image/jpeg")},
    )

    risk_res = await client.get(f"/projects/{p2['id']}/risk", headers=h2)
    assert risk_res.status_code == 200
    report = risk_res.json()["data"]

    dup_sig = next(s for s in report["signals"] if s["signal_name"] == "Duplicate Media")
    assert dup_sig["triggered"] is True
    assert dup_sig["score_contribution"] == 20.0
    assert "Similar media or identical cryptographic hash" in dup_sig["explanation"]


@pytest.mark.asyncio
async def test_suspicious_metadata_signal(client: AsyncClient):
    """Test Suspicious Metadata signal (+15) when photo editing software is recorded."""
    proj, headers = await setup_test_project(client)
    proj_id = proj["id"]

    await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        headers=headers,
        data={
            "title": "Edited Photo",
            "evidence_type": "BEFORE",
            "metadata_summary": '{"make": "Adobe", "software": "Adobe Photoshop CC 2024"}',
        },
        files={"file": ("photoshop.jpg", io.BytesIO(b"edited picture"), "image/jpeg")},
    )

    risk_res = await client.get(f"/projects/{proj_id}/risk", headers=headers)
    assert risk_res.status_code == 200
    report = risk_res.json()["data"]

    meta_sig = next(s for s in report["signals"] if s["signal_name"] == "Suspicious Metadata")
    assert meta_sig["triggered"] is True
    assert meta_sig["score_contribution"] == 15.0
    assert "photoshop" in meta_sig["explanation"].lower()


@pytest.mark.asyncio
async def test_high_project_value_and_audit_trigger(client: AsyncClient):
    """Test High Project Value (+10) and audit recommendation triggered by threshold."""
    proj, headers = await setup_test_project(client, budget=2500000.0)  # 25 Lakhs (>= 10 Lakhs threshold)
    proj_id = proj["id"]

    risk_res = await client.get(f"/projects/{proj_id}/risk", headers=headers)
    assert risk_res.status_code == 200
    report = risk_res.json()["data"]

    val_sig = next(s for s in report["signals"] if s["signal_name"] == "High Project Value")
    assert val_sig["triggered"] is True
    assert val_sig["score_contribution"] == 10.0

    # Must trigger audit recommendation due to high project value
    assert report["audit_trigger"]["audit_recommended"] is True
    assert "HIGH_PROJECT_VALUE" in report["audit_trigger"]["triggers"]


@pytest.mark.asyncio
async def test_previous_disputes_signal(client: AsyncClient, db_session: AsyncSession):
    """Test Previous Disputes signal (+15)."""
    proj, headers = await setup_test_project(client)
    proj_id = uuid.UUID(proj["id"])

    # Insert a dispute directly
    # Need a user to raise dispute
    dispute = Dispute(
        project_id=proj_id,
        raised_by_id=uuid.UUID(proj["created_by_id"]),
        reason="Donor flagged non-delivery of expected filtration unit.",
        status=DisputeStatus.OPEN,
    )
    db_session.add(dispute)
    await db_session.commit()

    risk_res = await client.get(f"/projects/{proj_id}/risk", headers=headers)
    assert risk_res.status_code == 200
    report = risk_res.json()["data"]

    disp_sig = next(s for s in report["signals"] if s["signal_name"] == "Previous Disputes")
    assert disp_sig["triggered"] is True
    assert disp_sig["score_contribution"] == 15.0
    assert "dispute(s) recorded" in disp_sig["explanation"]


@pytest.mark.asyncio
async def test_clamping_and_high_risk_audit_recommendation(client: AsyncClient):
    """Test multiple risk signals cumulate, clamp to 100, and trigger HIGH_RISK audit."""
    proj, headers = await setup_test_project(client, budget=2000000.0)  # High value (+10)
    proj_id = proj["id"]

    # 1. Location mismatch (+25)
    await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        headers=headers,
        data={
            "title": "Mismatched Site",
            "evidence_type": "BEFORE",
            "latitude": 28.0000,  # Far away
            "longitude": 75.7873,
            "metadata_summary": '{"software": "Photoshop CC"}',  # Suspicious metadata (+15)
        },
        files={"file": ("site.jpg", io.BytesIO(b"mismatched site photo"), "image/jpeg")},
    )

    # 2. Financial discrepancy (+25)
    await client.post(
        f"/api/v1/projects/{proj_id}/financial-evidence",
        headers=headers,
        data={
            "document_type": "BILL",
            "claimed_amount": 1000000.0,
        },
        files={"file": ("bill.pdf", io.BytesIO(b"Total: INR 100,000.00"), "application/pdf")},
    )

    # Cumulative score will be: Location(25) + Financial(25) + Metadata(15) + High Value(10) + Missing Timeline(15) = 90
    risk_res = await client.get(f"/projects/{proj_id}/risk", headers=headers)
    assert risk_res.status_code == 200
    report = risk_res.json()["data"]

    assert report["risk_score"] >= 60.0
    assert report["risk_score"] <= 100.0
    assert report["risk_level"] == "HIGH"
    assert report["audit_trigger"]["audit_recommended"] is True
    assert "HIGH_RISK_SCORE" in report["audit_trigger"]["triggers"]
    assert len(report["reasons"]) >= 3
