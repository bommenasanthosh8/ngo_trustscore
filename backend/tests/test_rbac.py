"""
Tests for Role-Based Access Control (RBAC):
- Roles: NGO, DONOR, AUDITOR, ADMIN
- Donors strictly forbidden (403 Forbidden) from modifying NGO/project/evidence data
- NGO users can create/view their projects and submit evidence
- Auditor and Admin permissions
- Unauthorized access (401) without credentials
"""
import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_unauthorized_access_rejected(client: AsyncClient):
    # Attempting to access protected NGO /projects/my without token
    res = await client.get("/api/v1/projects/my")
    assert res.status_code == 401
    assert res.json()["success"] is False


@pytest.mark.asyncio
async def test_donor_forbidden_from_creating_projects(client: AsyncClient, auth_headers):
    donor_id = uuid.uuid4()
    headers = auth_headers(donor_id, role="DONOR", email="donor@test.com")

    project_payload = {
        "title": "Unauthorized Donor Project",
        "project_type": "EDUCATION",
        "verification_model": "PERMANENT",
    }
    # DONOR attempts to create project -> HTTP 403 Forbidden
    res = await client.post("/api/v1/projects/", json=project_payload, headers=headers)
    assert res.status_code == 403
    assert res.json()["success"] is False
    assert "Access denied" in res.json()["error"]


@pytest.mark.asyncio
async def test_donor_forbidden_from_submitting_evidence(client: AsyncClient, auth_headers):
    donor_id = uuid.uuid4()
    headers = auth_headers(donor_id, role="DONOR", email="donor@test.com")

    # DONOR attempts to submit evidence -> HTTP 403 Forbidden
    res = await client.post("/api/v1/evidence/", json={}, headers=headers)
    assert res.status_code == 403
    assert res.json()["success"] is False


@pytest.mark.asyncio
async def test_donor_forbidden_from_auditor_cases(client: AsyncClient, auth_headers):
    donor_id = uuid.uuid4()
    headers = auth_headers(donor_id, role="DONOR", email="donor@test.com")

    # DONOR attempts to view audit cases -> HTTP 403 Forbidden
    res = await client.get("/api/v1/audit/cases", headers=headers)
    assert res.status_code == 403
    assert res.json()["success"] is False


@pytest.mark.asyncio
async def test_ngo_allowed_to_create_project(client: AsyncClient):
    # 1. Register NGO user
    reg_payload = {
        "email": "lead@greenearth.org",
        "password": "StrongPassword123!",
        "full_name": "Rohan Patel",
        "role": "NGO",
        "organization_name": "Green Earth Foundation",
        "registration_number": "NGO-GE-2026",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201

    # 2. Login to get token
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "lead@greenearth.org", "password": "StrongPassword123!"},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create project
    proj_payload = {
        "title": "Solar Powered Wells",
        "description": "Providing clean energy water pumps in arid areas",
        "project_type": "INFRASTRUCTURE",
        "verification_model": "PERMANENT",
        "total_budget": 500000.0,
        "location": {
            "latitude": 26.9124,
            "longitude": 75.7873,
            "location_name": "Jaipur Rural Site",
        },
    }
    create_res = await client.post("/api/v1/projects/", json=proj_payload, headers=headers)
    assert create_res.status_code == 201
    proj_data = create_res.json()["data"]
    assert proj_data["title"] == "Solar Powered Wells"
    assert proj_data["status"] == "CREATED"

    # 4. List my projects
    my_res = await client.get("/api/v1/projects/my", headers=headers)
    assert my_res.status_code == 200
    my_list = my_res.json()["data"]
    assert len(my_list) >= 1
    assert my_list[0]["title"] == "Solar Powered Wells"


@pytest.mark.asyncio
async def test_auditor_and_admin_permissions(client: AsyncClient, auth_headers):
    # Auditor access
    auditor_id = uuid.uuid4()
    auditor_headers = auth_headers(auditor_id, role="AUDITOR", email="auditor@gov.in")
    audit_res = await client.get("/api/v1/audit/cases", headers=auditor_headers)
    assert audit_res.status_code == 200

    # Admin access
    admin_id = uuid.uuid4()
    admin_headers = auth_headers(admin_id, role="ADMIN", email="admin@gov.in")
    admin_res = await client.get("/api/v1/audit/cases", headers=admin_headers)
    assert admin_res.status_code == 200
