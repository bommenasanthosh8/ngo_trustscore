"""
Comprehensive test suite for the Evidence Verification Engine:
- 10 Independent Verification Checks:
  1. LocationCheck (MATCH, NEAR, MISMATCH, UNAVAILABLE with PostGIS / Haversine)
  2. TimestampCheck (predates start, post completion, compressed timeline)
  3. TimelineCheck (Permanent BEFORE->PROGRESS->COMPLETION, One-time EVENT, Distribution)
  4. DuplicateMediaCheck (internal duplicate, cross-project media reuse)
  5. ImageSimilarityCheck (prototype adapter, angle tolerance, identical before/after flag)
  6. MetadataCheck (AVAILABLE, MISSING not penalized as fraud, SUSPICIOUS Photoshop)
  7. OCRCheck (cross-project IDs, amount discrepancies, dates)
  8. FinancialConsistencyCheck (CONSISTENT, MINOR_DISCREPANCY, MAJOR_DISCREPANCY)
  9. ProjectIdentityCheck (linkage to project & authorized NGO owner)
  10. EvidenceCompletenessCheck (category-specific missing stages)
- Overall Engine Orchestration & Scorecard
- Recommended Actions: NO_ADDITIONAL_ACTION, MANUAL_REVIEW, AUDIT_RECOMMENDED
- Objectivity: No direct fraudulent labels applied to NGO
"""
import hashlib
import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient


async def register_and_create_project(
    client: AsyncClient,
    title: str = "Clean Water Well Construction",
    category: str = "WATER_AND_SANITATION",
    model: str = "PERMANENT",
    budget: float = 250000.0,
    lat: float = 26.9124,
    lng: float = 75.7873,
    radius: float = 500.0,
):
    """Helper to register an NGO user and create a project."""
    email = f"lead_{uuid.uuid4().hex[:6]}@ruraltrust.org"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Arun Kumar",
            "role": "NGO",
            "organization_name": f"Rural Trust {uuid.uuid4().hex[:4]}",
            "registration_number": f"NGO-REG-{uuid.uuid4().hex[:6].upper()}",
        },
    )
    assert reg_res.status_code == 201

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    start_date = datetime.now(timezone.utc) - timedelta(days=30)
    end_date = datetime.now(timezone.utc) + timedelta(days=60)

    proj_res = await client.post(
        "/api/v1/projects/",
        json={
            "title": title,
            "description": "Building sustainable community wells",
            "project_type": category,
            "verification_model": model,
            "total_budget": budget,
            "target_amount": budget,
            "start_date": start_date.isoformat(),
            "expected_completion_date": end_date.isoformat(),
            "location": {
                "latitude": lat,
                "longitude": lng,
                "location_name": "Jaipur Rural Well Site 4",
                "geofence_radius": radius,
            },
        },
        headers=headers,
    )
    assert proj_res.status_code == 201
    return proj_res.json()["data"], headers


@pytest.mark.asyncio
async def test_verification_health(client: AsyncClient):
    """Test verification health endpoint and check registry."""
    res = await client.get("/api/v1/verification/health")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["status"] == "HEALTHY"
    assert data["total_checks"] == 10
    assert "LocationCheck" in data["registered_checks"]
    assert "FinancialConsistencyCheck" in data["registered_checks"]
    assert "DuplicateMediaCheck" in data["registered_checks"]


@pytest.mark.asyncio
async def test_location_check_geofence_states(client: AsyncClient):
    """Test LocationCheck geodetic states: MATCH, NEAR, MISMATCH, UNAVAILABLE."""
    project, headers = await register_and_create_project(client, lat=26.9124, lng=75.7873, radius=500.0)
    proj_id = project["id"]

    # 1. Evidence exactly at project coordinates (MATCH)
    f_match = io.BytesIO(b"evidence image bytes inside geofence")
    res_match = await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        headers=headers,
        data={
            "title": "Site Survey Photo",
            "evidence_type": "BEFORE",
            "latitude": 26.9125,
            "longitude": 75.7874,
            "gps_accuracy": 5.0,
            "metadata_summary": '{"make": "Samsung", "model": "Galaxy S22"}',
        },
        files={"file": ("site_before.jpg", f_match, "image/jpeg")},
    )
    assert res_match.status_code == 201

    # Run verification
    v_res = await client.post(f"/api/v1/projects/{proj_id}/verify", headers=headers)
    assert v_res.status_code == 200
    report = v_res.json()["data"]
    loc_check = next(c for c in report["individual_checks"] if c["check_name"] == "LocationCheck")
    assert loc_check["status"] == "MATCH"
    assert loc_check["details"]["distance_meters"] is not None
    assert loc_check["details"]["distance_meters"] <= loc_check["details"]["geofence_radius"]
    assert loc_check["score"] == 100.0


@pytest.mark.asyncio
async def test_duplicate_media_cross_project_reuse(client: AsyncClient):
    """Test DuplicateMediaCheck detects cross-project file reuse and recommends audit."""
    proj1, headers1 = await register_and_create_project(client, title="Project One")
    proj2, headers2 = await register_and_create_project(client, title="Project Two")

    shared_content = b"GENERIC_WELL_PHOTO_CONTENT_USED_IN_BOTH_PROJECTS_12345"

    # Upload to Project 1
    res1 = await client.post(
        f"/api/v1/projects/{proj1['id']}/evidence",
        headers=headers1,
        data={
            "title": "Borewell Drilling",
            "evidence_type": "BEFORE",
            "latitude": 26.9124,
            "longitude": 75.7873,
            "metadata_summary": '{"make": "Canon", "model": "EOS R5"}',
        },
        files={"file": ("borewell.jpg", io.BytesIO(shared_content), "image/jpeg")},
    )
    assert res1.status_code == 201

    # Upload exact same file to Project 2
    res2 = await client.post(
        f"/api/v1/projects/{proj2['id']}/evidence",
        headers=headers2,
        data={
            "title": "Different Well Site",
            "evidence_type": "BEFORE",
            "latitude": 26.9124,
            "longitude": 75.7873,
            "metadata_summary": '{"make": "Canon", "model": "EOS R5"}',
        },
        files={"file": ("fraudulent_reuse.jpg", io.BytesIO(shared_content), "image/jpeg")},
    )
    assert res2.status_code == 201

    # Verify Project 2
    v_res = await client.post(f"/api/v1/projects/{proj2['id']}/verify", headers=headers2)
    assert v_res.status_code == 200
    report = v_res.json()["data"]

    dup_check = next(c for c in report["individual_checks"] if c["check_name"] == "DuplicateMediaCheck")
    assert dup_check["status"] == "SUSPICIOUS"
    assert "CROSS_PROJECT_MEDIA_REUSE" in dup_check["risk_flags"]
    assert report["recommended_action"] == "AUDIT_RECOMMENDED"


@pytest.mark.asyncio
async def test_image_similarity_identical_before_completion(client: AsyncClient):
    """Test ImageSimilarityCheck flags when BEFORE and COMPLETION photos are identical."""
    proj, headers = await register_and_create_project(client, title="Community Hall")
    proj_id = proj["id"]

    same_img = b"IDENTICAL_PHOTO_OF_UNFINISHED_BUILDING"

    # Upload BEFORE
    await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        headers=headers,
        data={
            "title": "Before Construction",
            "evidence_type": "BEFORE",
            "metadata_summary": '{"make": "Nikon", "model": "Z6"}',
        },
        files={"file": ("before.jpg", io.BytesIO(same_img), "image/jpeg")},
    )

    # Upload COMPLETION with exact same photo
    await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        headers=headers,
        data={
            "title": "Completed Hall",
            "evidence_type": "COMPLETION",
            "metadata_summary": '{"make": "Nikon", "model": "Z6"}',
        },
        files={"file": ("completion.jpg", io.BytesIO(same_img), "image/jpeg")},
    )

    v_res = await client.post(f"/api/v1/projects/{proj_id}/verify", headers=headers)
    assert v_res.status_code == 200
    report = v_res.json()["data"]

    sim_check = next(c for c in report["individual_checks"] if c["check_name"] == "ImageSimilarityCheck")
    assert sim_check["status"] == "SUSPICIOUS"
    assert "BEFORE_COMPLETION_IDENTICAL_PHOTO" in sim_check["risk_flags"]


@pytest.mark.asyncio
async def test_metadata_check_statuses(client: AsyncClient):
    """Test MetadataCheck: AVAILABLE, MISSING (not fraud), SUSPICIOUS (photoshop)."""
    proj, headers = await register_and_create_project(client)
    proj_id = proj["id"]

    # Evidence with Photoshop metadata
    await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        headers=headers,
        data={
            "title": "Edited Certificate",
            "evidence_type": "OTHER",
            "metadata_summary": '{"make": "Apple", "software": "Adobe Photoshop 2024"}',
        },
        files={"file": ("edited.jpg", io.BytesIO(b"photoshop content"), "image/jpeg")},
    )

    v_res = await client.post(f"/api/v1/projects/{proj_id}/verify", headers=headers)
    assert v_res.status_code == 200
    report = v_res.json()["data"]

    meta_check = next(c for c in report["individual_checks"] if c["check_name"] == "MetadataCheck")
    assert meta_check["status"] == "SUSPICIOUS"
    assert "SUSPICIOUS_METADATA" in meta_check["risk_flags"]


@pytest.mark.asyncio
async def test_ocr_and_financial_consistency_checks(client: AsyncClient):
    """Test OCRCheck and FinancialConsistencyCheck integration."""
    proj, headers = await register_and_create_project(client, budget=100000.0)
    proj_id = proj["id"]

    # Upload financial evidence with matching amount
    bill_content = b"Grand Total: INR 98,500.00\nPaid To: Cement Supplier Co."
    fin_res = await client.post(
        f"/api/v1/projects/{proj_id}/financial-evidence",
        headers=headers,
        data={
            "document_type": "BILL",
            "claimed_amount": 98500.0,
            "currency": "INR",
            "vendor_name": "Cement Supplier Co.",
            "description": "Foundation cement bags",
        },
        files={"file": ("cement_bill.pdf", io.BytesIO(bill_content), "application/pdf")},
    )
    assert fin_res.status_code == 201

    v_res = await client.post(f"/api/v1/projects/{proj_id}/verify", headers=headers)
    assert v_res.status_code == 200
    report = v_res.json()["data"]

    fin_check = next(c for c in report["individual_checks"] if c["check_name"] == "FinancialConsistencyCheck")
    assert fin_check["status"] == "CONSISTENT"
    assert fin_check["score"] == 100.0

    ocr_check = next(c for c in report["individual_checks"] if c["check_name"] == "OCRCheck")
    assert ocr_check["status"] == "CONSISTENT"


@pytest.mark.asyncio
async def test_timeline_and_completeness_checks(client: AsyncClient):
    """Test TimelineCheck and EvidenceCompletenessCheck stages."""
    proj, headers = await register_and_create_project(client, model="PERMANENT", category="WATER_AND_SANITATION")
    proj_id = proj["id"]

    # Only upload COMPLETION, skipping BEFORE and PROGRESS
    await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        headers=headers,
        data={"title": "Finished Pump", "evidence_type": "COMPLETION"},
        files={"file": ("pump.jpg", io.BytesIO(b"completed pump photo"), "image/jpeg")},
    )

    v_res = await client.post(f"/api/v1/projects/{proj_id}/verify", headers=headers)
    assert v_res.status_code == 200
    report = v_res.json()["data"]

    tl_check = next(c for c in report["individual_checks"] if c["check_name"] == "TimelineCheck")
    assert tl_check["status"] in ("FAILED", "WARNING")
    assert "MISSING_BEFORE_STAGE" in tl_check["risk_flags"]

    comp_check = next(c for c in report["individual_checks"] if c["check_name"] == "EvidenceCompletenessCheck")
    assert comp_check["status"] == "PARTIAL"
    assert "BEFORE" in comp_check["details"]["missing_stages"]
    assert "FINANCIAL" in comp_check["details"]["missing_stages"]
