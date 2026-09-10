"""
Tests for Evidence Collection Module:
- File validation (types, size limits, dangerous extensions)
- SHA-256 hash generation accuracy
- Authorization (NGO owner vs donor vs foreign NGO)
- GPS capture vs LOCATION_UNAVAILABLE (no coordinate fabrication)
- Timestamps distinction (captured_at vs uploaded_at)
- Evidence immutability & correction history (supersedes_id)
- Project evidence listing and chronological timeline
- Secure file download access control
"""
import hashlib
import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient


async def create_test_project_with_ngo(client: AsyncClient):
    """Helper to create an NGO, an authenticated NGO user, and a project."""
    # 1. Register NGO user
    ngo_email = f"evidence_lead_{uuid.uuid4().hex[:6]}@ruralwater.org"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": ngo_email,
            "password": "Password123!",
            "full_name": "Deepak Sharma",
            "role": "NGO",
            "organization_name": f"Rural Water Mission {uuid.uuid4().hex[:4]}",
            "registration_number": f"NGO-RWM-{uuid.uuid4().hex[:6].upper()}",
        },
    )
    assert reg_res.status_code == 201

    # 2. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": ngo_email, "password": "Password123!"},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create Infrastructure Project
    proj_res = await client.post(
        "/api/v1/projects/",
        json={
            "title": "Borewell Construction at Barmer",
            "description": "Drilling deep solar borewell for 500 households",
            "project_type": "INFRASTRUCTURE",
            "verification_model": "PERMANENT",
            "total_budget": 800000.0,
            "location": {
                "latitude": 25.7532,
                "longitude": 71.3967,
                "location_name": "Barmer Deep Well Site",
                "geofence_radius": 600.0,
            },
        },
        headers=headers,
    )
    assert proj_res.status_code == 201
    project_data = proj_res.json()["data"]

    return {
        "headers": headers,
        "ngo_email": ngo_email,
        "project_id": project_data["id"],
        "project_code": project_data["project_code"],
    }


@pytest.mark.asyncio
async def test_upload_evidence_success_and_hash_generation(client: AsyncClient):
    env = await create_test_project_with_ngo(client)
    project_id = env["project_id"]
    headers = env["headers"]

    # Sample photo bytes
    photo_content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"mock_photo_data_for_testing" * 20
    expected_hash = hashlib.sha256(photo_content).hexdigest()

    captured_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()

    files = {
        "file": ("site_before_drilling.jpg", io.BytesIO(photo_content), "image/jpeg"),
    }
    data = {
        "title": "Site Inspection Before Drilling",
        "evidence_type": "BEFORE",
        "description": "Baseline geographical terrain before starting drilling operations.",
        "captured_at": captured_time,
        "latitude": "25.7535",
        "longitude": "71.3970",
        "gps_accuracy": "4.5",
        "metadata_summary": '{"camera": "Sony Alpha", "operator": "Deepak"}',
    }

    res = await client.post(
        f"/api/v1/projects/{project_id}/evidence",
        files=files,
        data=data,
        headers=headers,
    )

    assert res.status_code == 201
    res_data = res.json()["data"]

    # Verify stored attributes
    assert res_data["project_id"] == project_id
    assert res_data["title"] == "Site Inspection Before Drilling"
    assert res_data["evidence_type"] == "BEFORE"
    assert res_data["file_hash_sha256"] == expected_hash
    assert res_data["file_size"] == len(photo_content)
    assert res_data["mime_type"] == "image/jpeg"
    assert res_data["original_filename"] == "site_before_drilling.jpg"
    assert "evidence/" in res_data["storage_key"]
    assert res_data["location_status"] == "CAPTURED"
    assert float(res_data["latitude"]) == 25.7535
    assert float(res_data["longitude"]) == 71.3970
    assert float(res_data["gps_accuracy"]) == 4.5
    assert res_data["captured_at"] is not None
    assert res_data["uploaded_at"] is not None
    # Verify captured_at and uploaded_at are distinct
    assert res_data["captured_at"] != res_data["uploaded_at"]


@pytest.mark.asyncio
async def test_donor_forbidden_from_uploading_evidence(client: AsyncClient, auth_headers):
    env = await create_test_project_with_ngo(client)
    project_id = env["project_id"]

    donor_id = uuid.uuid4()
    donor_headers = auth_headers(donor_id, role="DONOR", email="donor@example.com")

    files = {
        "file": ("test.jpg", io.BytesIO(b"content"), "image/jpeg"),
    }
    data = {
        "title": "Donor Unauthorized Evidence",
        "evidence_type": "PROGRESS",
    }

    res = await client.post(
        f"/api/v1/projects/{project_id}/evidence",
        files=files,
        data=data,
        headers=donor_headers,
    )

    assert res.status_code == 403
    assert "Access denied" in res.json()["error"] or "Only registered NGO" in res.json()["error"]


@pytest.mark.asyncio
async def test_foreign_ngo_forbidden_from_uploading_to_another_project(client: AsyncClient):
    env = await create_test_project_with_ngo(client)
    project_id = env["project_id"]

    # Register a second NGO
    ngo2_email = f"ngo2_{uuid.uuid4().hex[:6]}@ngo.org"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": ngo2_email,
            "password": "Password123!",
            "full_name": "Another NGO Lead",
            "role": "NGO",
            "organization_name": f"Other NGO {uuid.uuid4().hex[:4]}",
            "registration_number": f"NGO-OTHER-{uuid.uuid4().hex[:6].upper()}",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": ngo2_email, "password": "Password123!"},
    )
    ngo2_headers = {"Authorization": f"Bearer {login_res.json()['data']['access_token']}"}

    files = {
        "file": ("test.jpg", io.BytesIO(b"content"), "image/jpeg"),
    }
    data = {
        "title": "Hijack Attempt",
        "evidence_type": "PROGRESS",
    }

    res = await client.post(
        f"/api/v1/projects/{project_id}/evidence",
        files=files,
        data=data,
        headers=ngo2_headers,
    )

    assert res.status_code == 403
    assert "projects owned by your organization" in res.json()["error"]


@pytest.mark.asyncio
async def test_file_validation_rejects_dangerous_extensions(client: AsyncClient):
    env = await create_test_project_with_ngo(client)
    project_id = env["project_id"]
    headers = env["headers"]

    # Attempting to upload a script (.sh or .exe)
    files = {
        "file": ("malicious_payload.sh", io.BytesIO(b"#!/bin/bash\nrm -rf /"), "application/x-sh"),
    }
    data = {
        "title": "Script upload attempt",
        "evidence_type": "OTHER",
    }

    res = await client.post(
        f"/api/v1/projects/{project_id}/evidence",
        files=files,
        data=data,
        headers=headers,
    )

    assert res.status_code == 400
    assert "security reasons" in res.json()["error"] or "not permitted" in res.json()["error"]


@pytest.mark.asyncio
async def test_gps_handling_location_unavailable_when_missing(client: AsyncClient):
    env = await create_test_project_with_ngo(client)
    project_id = env["project_id"]
    headers = env["headers"]

    # Upload evidence WITHOUT GPS coordinates (e.g. location permission denied on device)
    files = {
        "file": ("indoor_invoice.pdf", io.BytesIO(b"%PDF-1.4 mock pdf data"), "application/pdf"),
    }
    data = {
        "title": "Pump Supplier Invoice",
        "evidence_type": "FINANCIAL",
        "description": "Invoice for submersible water pump",
    }

    res = await client.post(
        f"/api/v1/projects/{project_id}/evidence",
        files=files,
        data=data,
        headers=headers,
    )

    assert res.status_code == 201
    item = res.json()["data"]

    # Must be marked LOCATION_UNAVAILABLE and must NOT fabricate coordinates
    assert item["location_status"] == "LOCATION_UNAVAILABLE"
    assert item["latitude"] is None
    assert item["longitude"] is None
    assert item["gps_accuracy"] is None


@pytest.mark.asyncio
async def test_evidence_immutability_and_superseding(client: AsyncClient):
    env = await create_test_project_with_ngo(client)
    project_id = env["project_id"]
    headers = env["headers"]

    # 1. Upload original evidence
    files1 = {
        "file": ("progress_pipe_laying_v1.jpg", io.BytesIO(b"original_pipe_photo"), "image/jpeg"),
    }
    data1 = {
        "title": "Pipe Laying Progress Week 1",
        "evidence_type": "PROGRESS",
        "description": "Initial pipe laying along trench.",
    }
    res1 = await client.post(
        f"/api/v1/projects/{project_id}/evidence",
        files=files1,
        data=data1,
        headers=headers,
    )
    assert res1.status_code == 201
    orig_id = res1.json()["data"]["id"]
    orig_hash = res1.json()["data"]["file_hash_sha256"]

    # 2. Upload a corrected file referencing the original via supersedes_id
    files2 = {
        "file": ("progress_pipe_laying_v2_corrected.jpg", io.BytesIO(b"corrected_higher_res_pipe_photo"), "image/jpeg"),
    }
    data2 = {
        "title": "Pipe Laying Progress Week 1 (Corrected High-Res)",
        "evidence_type": "PROGRESS",
        "description": "Re-uploaded with clear pipeline depth markings.",
        "supersedes_id": orig_id,
    }
    res2 = await client.post(
        f"/api/v1/projects/{project_id}/evidence",
        files=files2,
        data=data2,
        headers=headers,
    )
    assert res2.status_code == 201
    revised_id = res2.json()["data"]["id"]
    assert revised_id != orig_id
    assert res2.json()["data"]["supersedes_id"] == orig_id

    # 3. Verify original record is completely preserved and untouched (immutability)
    get_orig = await client.get(f"/api/v1/evidence/{orig_id}", headers=headers)
    assert get_orig.status_code == 200
    assert get_orig.json()["data"]["id"] == orig_id
    assert get_orig.json()["data"]["file_hash_sha256"] == orig_hash
    assert get_orig.json()["data"]["title"] == "Pipe Laying Progress Week 1"


@pytest.mark.asyncio
async def test_evidence_timeline_and_milestones(client: AsyncClient):
    env = await create_test_project_with_ngo(client)
    project_id = env["project_id"]
    headers = env["headers"]

    now = datetime.now(timezone.utc)

    # 1. Upload BEFORE evidence (captured 3 days ago)
    await client.post(
        f"/api/v1/projects/{project_id}/evidence",
        files={"file": ("terrain.jpg", io.BytesIO(b"terrain_bytes"), "image/jpeg")},
        data={
            "title": "Pre-construction Site Terrain",
            "evidence_type": "BEFORE",
            "captured_at": (now - timedelta(days=3)).isoformat(),
        },
        headers=headers,
    )

    # 2. Upload PROGRESS evidence (captured 1 day ago)
    await client.post(
        f"/api/v1/projects/{project_id}/evidence",
        files={"file": ("drilling.jpg", io.BytesIO(b"drilling_bytes"), "image/jpeg")},
        data={
            "title": "Rig Drilling at 150ft",
            "evidence_type": "PROGRESS",
            "captured_at": (now - timedelta(days=1)).isoformat(),
        },
        headers=headers,
    )

    # 3. Upload COMPLETION evidence (captured today)
    await client.post(
        f"/api/v1/projects/{project_id}/evidence",
        files={"file": ("well_operational.jpg", io.BytesIO(b"completion_bytes"), "image/jpeg")},
        data={
            "title": "Wellhead Functional & Pumping Water",
            "evidence_type": "COMPLETION",
            "captured_at": now.isoformat(),
        },
        headers=headers,
    )

    # 4. Fetch Timeline
    timeline_res = await client.get(
        f"/api/v1/projects/{project_id}/evidence/timeline",
        headers=headers,
    )
    assert timeline_res.status_code == 200
    timeline_data = timeline_res.json()["data"]

    assert timeline_data["total_items"] == 3
    assert timeline_data["milestone_summary"]["BEFORE"] == 1
    assert timeline_data["milestone_summary"]["PROGRESS"] == 1
    assert timeline_data["milestone_summary"]["COMPLETION"] == 1

    # Verify chronological order (earliest captured_at first)
    items = timeline_data["timeline"]
    assert items[0]["evidence_type"] == "BEFORE"
    assert items[1]["evidence_type"] == "PROGRESS"
    assert items[2]["evidence_type"] == "COMPLETION"


@pytest.mark.asyncio
async def test_secure_file_download_access_control(client: AsyncClient):
    env = await create_test_project_with_ngo(client)
    project_id = env["project_id"]
    headers = env["headers"]

    content = b"PDF_REPORT_CONTENT_VERIFIED_AUTHENTIC"
    files = {
        "file": ("lab_water_test_report.pdf", io.BytesIO(content), "application/pdf"),
    }
    data = {
        "title": "Water Quality Lab Report",
        "evidence_type": "COMPLETION",
    }

    upload_res = await client.post(
        f"/api/v1/projects/{project_id}/evidence",
        files=files,
        data=data,
        headers=headers,
    )
    assert upload_res.status_code == 201
    evidence_id = upload_res.json()["data"]["id"]

    # 1. Unauthenticated download rejected (401)
    unauth_res = await client.get(f"/api/v1/evidence/{evidence_id}/file")
    assert unauth_res.status_code == 401

    # 2. Authenticated authorized download succeeded
    dl_res = await client.get(f"/api/v1/evidence/{evidence_id}/file", headers=headers)
    assert dl_res.status_code == 200
    assert dl_res.content == content
    assert "application/pdf" in dl_res.headers["content-type"]

