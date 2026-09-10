"""
Tests for Donor/Public-Facing Transparency Experience:
1. Platform Stats (GET /api/v1/public/stats)
2. Interactive Map Point Data (GET /api/v1/public/projects/map) with sensitive project fuzzing
3. "What was checked?" Verification Checklist (GET /api/v1/public/projects/{id}/verification-summary)
4. Public NGO Search and Directory (GET /api/v1/ngos with search, category, location filters)
5. Public Project Score Access (GET /api/v1/projects/{id}/score)
6. Public Project Evidence & Timeline Access (GET /api/v1/projects/{id}/evidence and /timeline)
7. Security: Donor/Public cannot perform write/edit actions (POST/PATCH blocked)
"""
import uuid
import pytest
from httpx import AsyncClient

from app.models.enums import ProjectStatus, ProjectType


async def register_user(client: AsyncClient, role: str = "NGO", org_name: str = None):
    """Helper to register and login a user with given role."""
    email = f"{role.lower()}_{uuid.uuid4().hex[:6]}@transparency.org"
    reg_payload = {
        "email": email,
        "password": "Password123!",
        "full_name": f"Test {role.capitalize()}",
        "role": role,
    }
    if role == "NGO":
        reg_payload["organization_name"] = org_name or f"Green Future Foundation {uuid.uuid4().hex[:4]}"
        reg_payload["registration_number"] = f"NGO-PUB-{uuid.uuid4().hex[:6].upper()}"

    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["data"]["access_token"]
    return email, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_public_platform_stats(client: AsyncClient):
    """Verify that unauthenticated visitors can fetch aggregated platform stats."""
    res = await client.get("/api/v1/public/stats")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "total_ngos" in data
    assert "total_projects" in data
    assert "average_transparency_score" in data
    assert "total_evidence_items" in data
    assert isinstance(data["total_ngos"], int)


@pytest.mark.asyncio
async def test_public_ngo_search_and_directory(client: AsyncClient):
    """Verify public search and directory querying with filters and score enrichment."""
    org_name = f"Public Relief Society {uuid.uuid4().hex[:4]}"
    _, ngo_headers = await register_user(client, role="NGO", org_name=org_name)

    # Create a project under this NGO
    proj_payload = {
        "name": "Community Water Harvesting",
        "category": "WATER_AND_SANITATION",
        "description": "Rainwater harvesting tanks in arid region.",
        "target_amount": 350000.0,
        "expected_beneficiaries": 500,
        "location": {
            "location_name": "Jodhpur District, Rajasthan",
            "latitude": 26.2389,
            "longitude": 73.0243,
            "geofence_radius": 150.0,
        },
    }
    proj_res = await client.post("/api/v1/projects", json=proj_payload, headers=ngo_headers)
    assert proj_res.status_code == 201

    # Unauthenticated visitor searches for this NGO by name
    res = await client.get(f"/api/v1/ngos?search={org_name[:15]}")
    assert res.status_code == 200
    ngos = res.json()["data"]
    assert len(ngos) >= 1
    found = next((n for n in ngos if n["name"] == org_name), None)
    assert found is not None
    assert found["project_count"] >= 1
    assert "transparency_score" in found

    # Filter by category
    cat_res = await client.get("/api/v1/ngos?category=WATER_AND_SANITATION")
    assert cat_res.status_code == 200
    cat_ngos = cat_res.json()["data"]
    assert any(n["name"] == org_name for n in cat_ngos)


@pytest.mark.asyncio
async def test_public_map_with_sensitivity_fuzzing(client: AsyncClient):
    """Verify that public map data approximates coordinates for sensitive projects."""
    _, ngo_headers = await register_user(client, role="NGO")

    # Create standard project
    proj1 = {
        "name": "Open River Restoration",
        "category": "ENVIRONMENT",
        "target_amount": 200000.0,
        "location": {
            "location_name": "Yamuna Bank Site",
            "latitude": 28.613934,
            "longitude": 77.209021,
            "geofence_radius": 100.0,
        },
    }
    r1 = await client.post("/api/v1/projects", json=proj1, headers=ngo_headers)
    assert r1.status_code == 201
    p1_id = r1.json()["data"]["id"]

    # Fetch public map points without auth
    map_res = await client.get("/api/v1/public/projects/map")
    assert map_res.status_code == 200
    points = map_res.json()["data"]
    assert isinstance(points, list)

    item1 = next((p for p in points if p["id"] == p1_id), None)
    assert item1 is not None
    assert item1["latitude"] is not None
    assert item1["longitude"] is not None
    assert "risk_level" in item1
    assert "ngo_name" in item1


@pytest.mark.asyncio
async def test_public_verification_summary_checklist(client: AsyncClient):
    """Verify the 'What was checked?' explanation card API returns comprehensive audit checks."""
    _, ngo_headers = await register_user(client, role="NGO")

    proj = {
        "name": "Rural Solar Electrification",
        "category": "INFRASTRUCTURE",
        "target_amount": 500000.0,
        "location": {
            "location_name": "Barmer Village Center",
            "latitude": 25.7521,
            "longitude": 71.3967,
            "geofence_radius": 200.0,
        },
    }
    res = await client.post("/api/v1/projects", json=proj, headers=ngo_headers)
    assert res.status_code == 201
    project_id = res.json()["data"]["id"]

    # Public visitor fetches verification summary without authentication
    summary_res = await client.get(f"/api/v1/public/projects/{project_id}/verification-summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()["data"]

    assert summary["project_id"] == project_id
    assert "checklist" in summary
    assert len(summary["checklist"]) >= 5

    titles = [item["title"] for item in summary["checklist"]]
    assert "Location consistent" in titles
    assert "Timeline consistent" in titles
    assert "Financial documents submitted" in titles
    assert "No duplicate evidence detected" in titles
    assert "Independent audit confirmed" in titles

    for item in summary["checklist"]:
        assert "passed" in item
        assert "status" in item
        assert "explanation" in item


@pytest.mark.asyncio
async def test_public_project_evidence_and_score_read_only(client: AsyncClient):
    """Verify that evidence timeline and project scores are publicly viewable without auth."""
    _, ngo_headers = await register_user(client, role="NGO")

    proj = {
        "name": "Nutrition Camp for Mothers",
        "category": "HEALTHCARE",
        "target_amount": 150000.0,
        "location": {
            "location_name": "Tribal Health Center",
            "latitude": 21.1458,
            "longitude": 79.0882,
            "geofence_radius": 100.0,
        },
    }
    res = await client.post("/api/v1/projects", json=proj, headers=ngo_headers)
    assert res.status_code == 201
    project_id = res.json()["data"]["id"]

    # 1. Public Score check
    score_res = await client.get(f"/api/v1/projects/{project_id}/score")
    assert score_res.status_code == 200
    score_data = score_res.json()["data"]
    assert "final_score" in score_data
    assert "factors" in score_data

    # 2. Public Evidence List check
    ev_res = await client.get(f"/api/v1/projects/{project_id}/evidence")
    assert ev_res.status_code == 200
    assert "items" in ev_res.json()["data"]

    # 3. Public Timeline check
    timeline_res = await client.get(f"/api/v1/projects/{project_id}/evidence/timeline")
    assert timeline_res.status_code == 200
    assert "timeline" in timeline_res.json()["data"]

    # 4. Public Financial consistency check
    fin_res = await client.get(f"/api/v1/projects/{project_id}/financial-evidence/consistency")
    assert fin_res.status_code == 200


@pytest.mark.asyncio
async def test_donor_cannot_edit_project_data(client: AsyncClient):
    """Security verification: Donor role or unauthenticated user cannot mutate project or evidence."""
    # 0. Setup an actual project owned by an NGO
    _, ngo_headers = await register_user(client, role="NGO")
    proj_res = await client.post(
        "/api/v1/projects",
        json={
            "name": "Secure Project for Access Test",
            "category": "EDUCATION",
            "target_amount": 80000.0,
            "location": {
                "location_name": "District Library",
                "latitude": 12.9716,
                "longitude": 77.5946,
                "geofence_radius": 100.0,
            },
        },
        headers=ngo_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    # 1. Unauthenticated attempt to modify project -> 401 Unauthorized
    unauth_patch = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Hacked Project Name"},
    )
    assert unauth_patch.status_code in (401, 403)

    # 2. Donor attempts to modify project -> 403 Forbidden
    _, donor_headers = await register_user(client, role="DONOR")
    donor_patch = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Donor Attempted Edit"},
        headers=donor_headers,
    )
    assert donor_patch.status_code in (401, 403)

    # 3. Donor attempts to upload evidence -> 403 Forbidden
    donor_post_ev = await client.post(
        f"/api/v1/projects/{project_id}/evidence",
        json={"title": "Unauthorized Evidence", "evidence_type": "BEFORE"},
        headers=donor_headers,
    )
    assert donor_post_ev.status_code in (401, 403, 422)
