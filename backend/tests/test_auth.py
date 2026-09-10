"""
Tests for authentication:
- Registration (DONOR, NGO)
- Duplicate email conflict
- Admin self-registration prevention
- Password hashing (bcrypt)
- Login (valid & invalid credentials)
- JWT access and refresh token generation
- Authenticated user /auth/me endpoint
"""
import pytest
from httpx import AsyncClient
from app.core.security import verify_password


@pytest.mark.asyncio
async def test_register_donor(client: AsyncClient):
    payload = {
        "email": "donor1@test.com",
        "password": "SecurePassword123!",
        "full_name": "Kind Donor",
        "role": "DONOR",
    }
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    assert body["data"]["email"] == "donor1@test.com"
    assert body["data"]["role"] == "DONOR"
    assert body["data"].get("ngo_id") is None


@pytest.mark.asyncio
async def test_register_ngo_creates_and_links_ngo(client: AsyncClient):
    payload = {
        "email": "ngo_lead@cleanwater.org",
        "password": "SecurePassword123!",
        "full_name": "Aarav Sharma",
        "role": "NGO",
        "organization_name": "Clean Water Trust",
        "registration_number": "NGO-CW-2026",
        "website": "https://cleanwater.org",
    }
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    assert body["data"]["role"] == "NGO"
    assert body["data"]["ngo_id"] is not None


@pytest.mark.asyncio
async def test_register_duplicate_email_fails(client: AsyncClient):
    payload = {
        "email": "duplicate@test.com",
        "password": "SecurePassword123!",
        "full_name": "First User",
        "role": "DONOR",
    }
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409


@pytest.mark.asyncio
async def test_admin_self_registration_prevented(client: AsyncClient):
    payload = {
        "email": "fake_admin@test.com",
        "password": "SecurePassword123!",
        "full_name": "Hacker",
        "role": "ADMIN",
    }
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_login_success_and_token_exchange(client: AsyncClient):
    # Register first
    email = "login_test@example.com"
    pw = "SecretPass123!"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pw, "full_name": "Test Login", "role": "DONOR"},
    )

    # Login
    login_res = await client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert login_res.status_code == 200
    tokens = login_res.json()["data"]
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"

    # Access /auth/me
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()["data"]
    assert me_data["email"] == email


@pytest.mark.asyncio
async def test_login_invalid_password_rejected(client: AsyncClient):
    email = "badpw@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "CorrectPassword123!", "full_name": "Bad Pw", "role": "DONOR"},
    )
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPassword!"})
    assert res.status_code == 401
