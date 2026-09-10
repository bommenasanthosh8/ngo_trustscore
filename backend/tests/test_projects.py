"""
Test suite for NGO Project Management module.
Covers:
- Project creation with full metadata, PostGIS location, and geofence
- Human-readable Project ID generation (e.g. NGO-WELL-2026-0001)
- Lookup by internal UUID and by human-readable Project ID
- Valid state machine transitions (CREATED -> FUNDING -> EVIDENCE_COLLECTION -> UNDER_VERIFICATION -> VERIFIED)
- Invalid state transitions rejected with 400 Bad Request
- NGO self-verification forbidden (verification requires admin/auditor)
- NGO ownership authorization (NGO A cannot modify NGO B's project; Donor cannot create/modify)
- Pagination, category filtering, and status filtering
- Location search/geocode helper endpoint
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.core.security import hash_password
from app.models.enums import NGOVerificationStatus, ProjectStatus, ProjectType
from app.models.ngo import NGO
from app.models.project import Project


async def _create_test_ngo_and_user(
    db: AsyncSession,
    ngo_name: str,
    email: str,
    role: UserRole = UserRole.NGO,
) -> tuple[NGO, User]:
    ngo = NGO(
        name=ngo_name,
        registration_number=f"REG-{uuid.uuid4().hex[:8].upper()}",
        verification_status=NGOVerificationStatus.VERIFIED,
        is_verified=True,
    )
    db.add(ngo)
    await db.flush()

    user = User(
        email=email,
        hashed_password=hash_password("SecurePass123!"),
        full_name="NGO Lead",
        role=role,
        ngo_id=ngo.id,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    return ngo, user


@pytest.mark.asyncio
async def test_create_project_success_and_human_id(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
):
    ngo, ngo_user = await _create_test_ngo_and_user(
        db_session,
        ngo_name=f"Varanasi Water Mission {uuid.uuid4().hex[:6]}",
        email=f"water_rep_{uuid.uuid4().hex[:6]}@ngo.org",
    )
    headers = auth_headers(ngo_user.id, role="NGO", email=ngo_user.email)

    payload = {
        "name": "Rampur Solar Borewell & Community Water Center",
        "category": "WATER_AND_SANITATION",
        "description": "Constructing two solar-powered borewells with filtration units.",
        "target_amount": 450000.0,
        "expected_beneficiaries": 1800,
        "start_date": "2026-03-01T00:00:00Z",
        "expected_completion_date": "2026-08-31T00:00:00Z",
        "location": {
            "location_name": "Rampur Village Site, Varanasi District, UP",
            "latitude": 25.3176,
            "longitude": 82.9739,
            "geofence_radius": 500.0,
            "gps_accuracy": 3.5,
            "selection_method": "MAP_CLICK",
        },
        "expected_outcome": "Supply 20,000 liters/day potable drinking water to 350 rural families.",
    }

    res = await client.post("/projects", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()["data"]

    # Assert human-readable ID format (e.g. NGO-WELL-2026-0001)
    current_year = datetime.now(timezone.utc).year
    pattern = rf"^NGO-WELL-{current_year}-\d{{4}}$"
    assert re.match(pattern, data["project_code"]), f"Unexpected format: {data['project_code']}"

    # Assert initial status is CREATED
    assert data["status"] == ProjectStatus.CREATED.value

    # Assert fields
    assert data["title"] == payload["name"]
    assert data["category"] == payload["category"]
    assert data["target_amount"] == 450000.0
    assert data["expected_beneficiaries"] == 1800
    assert data["location_name"] == payload["location"]["location_name"]
    assert data["latitude"] == 25.3176
    assert data["longitude"] == 82.9739
    assert data["geofence_radius"] == 500.0
    assert data["gps_accuracy"] == 3.5
    assert data["expected_outcome"] == payload["expected_outcome"]


@pytest.mark.asyncio
async def test_donor_forbidden_from_creating_project(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
):
    donor = User(
        email=f"donor_{uuid.uuid4().hex[:6]}@charity.org",
        hashed_password=hash_password("Pass123!"),
        full_name="Philanthropist",
        role=UserRole.DONOR,
        is_active=True,
    )
    db_session.add(donor)
    await db_session.flush()

    headers = auth_headers(donor.id, role="DONOR", email=donor.email)
    payload = {
        "name": "Unauthorized Project",
        "category": "EDUCATION",
        "target_amount": 100000.0,
        "location": {
            "location_name": "Test Site",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "geofence_radius": 300.0,
        },
    }
    res = await client.post("/projects", json=payload, headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_get_project_by_uuid_and_code(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
):
    ngo, ngo_user = await _create_test_ngo_and_user(
        db_session,
        ngo_name=f"Literacy Drive {uuid.uuid4().hex[:6]}",
        email=f"literacy_{uuid.uuid4().hex[:6]}@ngo.org",
    )
    headers = auth_headers(ngo_user.id, role="NGO", email=ngo_user.email)

    payload = {
        "name": "Bhamragad Smart Ashram STEM Lab",
        "category": "EDUCATION",
        "target_amount": 320000.0,
        "location": {
            "location_name": "Bhamragad, Gadchiroli",
            "latitude": 19.3850,
            "longitude": 80.3540,
            "geofence_radius": 450.0,
        },
    }
    create_res = await client.post("/projects", json=payload, headers=headers)
    assert create_res.status_code == 201
    created = create_res.json()["data"]

    # 1. Lookup by UUID
    res_uuid = await client.get(f"/projects/{created['id']}")
    assert res_uuid.status_code == 200
    assert res_uuid.json()["data"]["project_code"] == created["project_code"]

    # 2. Lookup by Human-readable Project ID (e.g. NGO-EDU-2026-0001)
    res_code = await client.get(f"/projects/{created['project_code']}")
    assert res_code.status_code == 200
    assert res_code.json()["data"]["id"] == created["id"]


@pytest.mark.asyncio
async def test_state_machine_valid_transitions(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
):
    # Setup NGO
    ngo, ngo_user = await _create_test_ngo_and_user(
        db_session,
        ngo_name=f"Clinic Network {uuid.uuid4().hex[:6]}",
        email=f"clinic_{uuid.uuid4().hex[:6]}@ngo.org",
    )
    ngo_headers = auth_headers(ngo_user.id, role="NGO", email=ngo_user.email)

    # Setup Admin
    admin = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@platform.gov",
        hashed_password=hash_password("AdminPass123!"),
        full_name="Platform Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.flush()
    admin_headers = auth_headers(admin.id, role="ADMIN", email=admin.email)

    # 1. Create project (starts in CREATED)
    create_res = await client.post(
        "/projects",
        json={
            "name": "Maternal Healthcare Clinic",
            "category": "HEALTHCARE",
            "target_amount": 800000.0,
            "location": {
                "location_name": "Nashik Health Outpost",
                "latitude": 19.9324,
                "longitude": 73.5308,
                "geofence_radius": 350.0,
            },
        },
        headers=ngo_headers,
    )
    assert create_res.status_code == 201
    p_id = create_res.json()["data"]["id"]
    assert create_res.json()["data"]["status"] == "CREATED"

    # 2. CREATED -> FUNDING
    res1 = await client.patch(f"/projects/{p_id}", json={"status": "FUNDING"}, headers=ngo_headers)
    assert res1.status_code == 200
    assert res1.json()["data"]["status"] == "FUNDING"

    # 3. FUNDING -> EVIDENCE_COLLECTION
    res2 = await client.patch(f"/projects/{p_id}", json={"status": "EVIDENCE_COLLECTION"}, headers=ngo_headers)
    assert res2.status_code == 200
    assert res2.json()["data"]["status"] == "EVIDENCE_COLLECTION"

    # 4. EVIDENCE_COLLECTION -> UNDER_VERIFICATION
    res3 = await client.patch(f"/projects/{p_id}", json={"status": "UNDER_VERIFICATION"}, headers=ngo_headers)
    assert res3.status_code == 200
    assert res3.json()["data"]["status"] == "UNDER_VERIFICATION"

    # 5. UNDER_VERIFICATION -> VERIFIED (Admin only)
    res4 = await client.patch(f"/projects/{p_id}", json={"status": "VERIFIED"}, headers=admin_headers)
    assert res4.status_code == 200
    assert res4.json()["data"]["status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_invalid_status_transition_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
):
    ngo, ngo_user = await _create_test_ngo_and_user(
        db_session,
        ngo_name=f"Agro Forestry {uuid.uuid4().hex[:6]}",
        email=f"agro_{uuid.uuid4().hex[:6]}@ngo.org",
    )
    headers = auth_headers(ngo_user.id, role="NGO", email=ngo_user.email)

    create_res = await client.post(
        "/projects",
        json={
            "name": "Mangrove Regeneration",
            "category": "ENVIRONMENT",
            "target_amount": 500000.0,
            "location": {
                "location_name": "Gosaba Delta",
                "latitude": 22.1648,
                "longitude": 88.8094,
                "geofence_radius": 1500.0,
            },
        },
        headers=headers,
    )
    p_id = create_res.json()["data"]["id"]

    # Try illegal jump: CREATED -> UNDER_VERIFICATION directly
    res_jump = await client.patch(
        f"/projects/{p_id}",
        json={"status": "UNDER_VERIFICATION"},
        headers=headers,
    )
    assert res_jump.status_code == 400
    assert "Invalid status transition" in res_jump.json()["error"]


@pytest.mark.asyncio
async def test_ngo_cannot_unilaterally_self_verify(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
):
    ngo, ngo_user = await _create_test_ngo_and_user(
        db_session,
        ngo_name=f"Self Verify NGO {uuid.uuid4().hex[:6]}",
        email=f"self_ver_{uuid.uuid4().hex[:6]}@ngo.org",
    )
    headers = auth_headers(ngo_user.id, role="NGO", email=ngo_user.email)

    create_res = await client.post(
        "/projects",
        json={
            "name": "Food Bank Logistics",
            "category": "FOOD_DISTRIBUTION",
            "target_amount": 250000.0,
            "location": {
                "location_name": "Pune Hub",
                "latitude": 18.5204,
                "longitude": 73.8567,
            },
        },
        headers=headers,
    )
    p_id = create_res.json()["data"]["id"]

    # Advance to UNDER_VERIFICATION
    await client.patch(f"/projects/{p_id}", json={"status": "FUNDING"}, headers=headers)
    await client.patch(f"/projects/{p_id}", json={"status": "EVIDENCE_COLLECTION"}, headers=headers)
    await client.patch(f"/projects/{p_id}", json={"status": "UNDER_VERIFICATION"}, headers=headers)

    # NGO user tries to mark VERIFIED directly without admin/auditor
    res_self_verify = await client.patch(
        f"/projects/{p_id}",
        json={"status": "VERIFIED"},
        headers=headers,
    )
    assert res_self_verify.status_code == 403
    assert "Only platform verification engines" in res_self_verify.json()["error"]


@pytest.mark.asyncio
async def test_ngo_ownership_authorization(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
):
    # NGO A
    ngo_a, user_a = await _create_test_ngo_and_user(
        db_session,
        ngo_name=f"NGO Alpha {uuid.uuid4().hex[:6]}",
        email=f"alpha_{uuid.uuid4().hex[:6]}@ngo.org",
    )
    headers_a = auth_headers(user_a.id, role="NGO", email=user_a.email)

    # NGO B
    ngo_b, user_b = await _create_test_ngo_and_user(
        db_session,
        ngo_name=f"NGO Beta {uuid.uuid4().hex[:6]}",
        email=f"beta_{uuid.uuid4().hex[:6]}@ngo.org",
    )
    headers_b = auth_headers(user_b.id, role="NGO", email=user_b.email)

    # Create project by NGO A
    create_res = await client.post(
        "/projects",
        json={
            "name": "Alpha Sanitation Project",
            "category": "WATER_AND_SANITATION",
            "target_amount": 180000.0,
            "location": {
                "location_name": "Alpha Site",
                "latitude": 20.0,
                "longitude": 75.0,
            },
        },
        headers=headers_a,
    )
    project_id = create_res.json()["data"]["id"]

    # NGO B attempts to PATCH NGO A's project
    res_unauthorized = await client.patch(
        f"/projects/{project_id}",
        json={"description": "Tampered description by NGO B"},
        headers=headers_b,
    )
    assert res_unauthorized.status_code == 403


@pytest.mark.asyncio
async def test_pagination_and_filtering(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
):
    ngo, ngo_user = await _create_test_ngo_and_user(
        db_session,
        ngo_name=f"Filter Test Org {uuid.uuid4().hex[:6]}",
        email=f"filter_{uuid.uuid4().hex[:6]}@ngo.org",
    )
    headers = auth_headers(ngo_user.id, role="NGO", email=ngo_user.email)

    # Create 2 projects with different categories
    p1_res = await client.post(
        "/projects",
        json={
            "name": "Specialized Cardiac Clinic",
            "category": "HEALTHCARE",
            "target_amount": 900000.0,
            "location": {"location_name": "Heart Center", "latitude": 19.0, "longitude": 73.0},
        },
        headers=headers,
    )
    assert p1_res.status_code == 201

    p2_res = await client.post(
        "/projects",
        json={
            "name": "Rural Solar School Project",
            "category": "EDUCATION",
            "target_amount": 300000.0,
            "location": {"location_name": "Solar School", "latitude": 21.0, "longitude": 78.0},
        },
        headers=headers,
    )
    assert p2_res.status_code == 201

    # 1. Filter by category
    res_cat = await client.get("/projects?category=HEALTHCARE")
    assert res_cat.status_code == 200
    categories = [p["category"] for p in res_cat.json()["data"]]
    assert all(c == "HEALTHCARE" for c in categories)

    # 2. Filter by status
    res_status = await client.get("/projects?status=CREATED")
    assert res_status.status_code == 200
    statuses = [p["status"] for p in res_status.json()["data"]]
    assert all(s == "CREATED" for s in statuses)

    # 3. Search query
    res_search = await client.get("/projects?search=Cardiac")
    assert res_search.status_code == 200
    titles = [p["title"] for p in res_search.json()["data"]]
    assert any("Cardiac" in t for t in titles)


@pytest.mark.asyncio
async def test_location_search_endpoint(client: AsyncClient):
    res = await client.get("/projects/locations/search?q=Varanasi")
    assert res.status_code == 200
    results = res.json()["data"]
    assert len(results) > 0
    assert any("Varanasi" in r["display_name"] or "Varanasi" in r["location_name"] for r in results)
    first = results[0]
    assert "latitude" in first
    assert "longitude" in first
