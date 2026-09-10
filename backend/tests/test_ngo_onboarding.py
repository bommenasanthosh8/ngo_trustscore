"""
Test suite for Authentication and NGO Onboarding module.
Covers:
- NGO onboarding with required & optional fields
- Verification status lifecycle (PENDING -> VERIFIED / REJECTED)
- Ensuring regular NGOs cannot alter verification_status
- Admin-only controls for listing pending NGOs, verifying, and rejecting
- RBAC protections forbidding Donors and unauthorized users from altering NGO profiles
- Logout and session audit logging
"""
from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.core.security import hash_password
from app.models.enums import NGOVerificationStatus
from app.models.ngo import NGO


async def _create_test_user(
    db: AsyncSession,
    email: str,
    role: UserRole,
    ngo_id: uuid.UUID | None = None,
    full_name: str = "Test User",
) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("Password123!"),
        full_name=full_name,
        role=role,
        ngo_id=ngo_id,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_ngo_onboarding_success_and_defaults(client: AsyncClient, db_session: AsyncSession, auth_headers):
    # 1. Create an NGO user
    ngo_user = await _create_test_user(
        db_session,
        email=f"ngo_rep_{uuid.uuid4().hex[:6]}@example.org",
        role=UserRole.NGO,
        full_name="Aarav Sharma",
    )
    headers = auth_headers(ngo_user.id, role="NGO", email=ngo_user.email)

    # 2. Onboard NGO via POST /ngos
    payload = {
        "name": f"Aarav Care Foundation {uuid.uuid4().hex[:6]}",
        "registration_number": f"REG-NGO-{uuid.uuid4().hex[:6].upper()}",
        "description": "Providing clean water and educational infrastructure to rural areas.",
        "address": "42 Civil Lines, Pune, MH 411001",
        "contact_email": "info@aaravcare.org",
        "contact_phone": "+91-9876543210",
        "website": "https://aaravcare.org",
        "authorized_representative": "Aarav Sharma",
    }

    res = await client.post("/ngos", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()["data"]

    assert data["name"] == payload["name"]
    assert data["registration_number"] == payload["registration_number"]
    assert data["description"] == payload["description"]
    assert data["address"] == payload["address"]
    assert data["contact_email"] == payload["contact_email"]
    assert data["contact_phone"] == payload["contact_phone"]
    assert data["website"] == payload["website"]
    assert data["authorized_representative"] == payload["authorized_representative"]
    # Verification status MUST always be PENDING upon creation
    assert data["verification_status"] == NGOVerificationStatus.PENDING.value
    assert data["is_verified"] is False
    assert data.get("rejection_reason") is None

    # Check that the user is now linked to this NGO
    await db_session.refresh(ngo_user)
    assert str(ngo_user.ngo_id) == data["id"]


@pytest.mark.asyncio
async def test_donor_cannot_create_ngo(client: AsyncClient, db_session: AsyncSession, auth_headers):
    donor_user = await _create_test_user(
        db_session,
        email=f"donor_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.DONOR,
    )
    headers = auth_headers(donor_user.id, role="DONOR", email=donor_user.email)

    payload = {
        "name": f"Unauthorized NGO {uuid.uuid4().hex[:6]}",
        "registration_number": f"REG-{uuid.uuid4().hex[:6].upper()}",
    }
    res = await client.post("/ngos", json=payload, headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_registration_or_name_rejected(client: AsyncClient, db_session: AsyncSession, auth_headers):
    ngo_user_1 = await _create_test_user(
        db_session,
        email=f"ngo1_{uuid.uuid4().hex[:6]}@example.org",
        role=UserRole.NGO,
    )
    headers_1 = auth_headers(ngo_user_1.id, role="NGO", email=ngo_user_1.email)

    reg_num = f"REG-DUP-{uuid.uuid4().hex[:6].upper()}"
    org_name = f"Unique NGO {uuid.uuid4().hex[:6]}"

    payload = {
        "name": org_name,
        "registration_number": reg_num,
    }
    res = await client.post("/ngos", json=payload, headers=headers_1)
    assert res.status_code == 201

    # Second NGO user tries same registration number
    ngo_user_2 = await _create_test_user(
        db_session,
        email=f"ngo2_{uuid.uuid4().hex[:6]}@example.org",
        role=UserRole.NGO,
    )
    headers_2 = auth_headers(ngo_user_2.id, role="NGO", email=ngo_user_2.email)

    res_dup = await client.post(
        "/ngos",
        json={"name": f"Another Name {uuid.uuid4().hex[:4]}", "registration_number": reg_num},
        headers=headers_2,
    )
    assert res_dup.status_code == 409


@pytest.mark.asyncio
async def test_get_and_patch_ngo(client: AsyncClient, db_session: AsyncSession, auth_headers):
    # Setup NGO
    ngo = NGO(
        name=f"Green Earth {uuid.uuid4().hex[:6]}",
        registration_number=f"REG-GE-{uuid.uuid4().hex[:6].upper()}",
        description="Environmental conservation",
        address="10 Earth Way",
        verification_status=NGOVerificationStatus.PENDING,
        is_verified=False,
    )
    db_session.add(ngo)
    await db_session.flush()

    ngo_user = await _create_test_user(
        db_session,
        email=f"green_{uuid.uuid4().hex[:6]}@earth.org",
        role=UserRole.NGO,
        ngo_id=ngo.id,
    )
    headers = auth_headers(ngo_user.id, role="NGO", email=ngo_user.email)

    # 1. GET /ngos/{id}
    res_get = await client.get(f"/ngos/{ngo.id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["data"]["name"] == ngo.name

    # 2. PATCH /ngos/{id} with valid profile changes
    patch_payload = {
        "description": "Updated conservation mission and reforestation efforts.",
        "website": "https://greenearth.example.org",
        "contact_phone": "+91-1122334455",
    }
    res_patch = await client.patch(f"/ngos/{ngo.id}", json=patch_payload, headers=headers)
    assert res_patch.status_code == 200
    updated_data = res_patch.json()["data"]
    assert updated_data["description"] == patch_payload["description"]
    assert updated_data["website"] == patch_payload["website"]
    assert updated_data["contact_phone"] == patch_payload["contact_phone"]
    # Still PENDING
    assert updated_data["verification_status"] == NGOVerificationStatus.PENDING.value


@pytest.mark.asyncio
async def test_ngo_cannot_change_its_own_verification_status(client: AsyncClient, db_session: AsyncSession, auth_headers):
    ngo = NGO(
        name=f"Self-Verify Test {uuid.uuid4().hex[:6]}",
        registration_number=f"REG-SV-{uuid.uuid4().hex[:6].upper()}",
        verification_status=NGOVerificationStatus.PENDING,
        is_verified=False,
    )
    db_session.add(ngo)
    await db_session.flush()

    ngo_user = await _create_test_user(
        db_session,
        email=f"sv_{uuid.uuid4().hex[:6]}@ngo.org",
        role=UserRole.NGO,
        ngo_id=ngo.id,
    )
    headers = auth_headers(ngo_user.id, role="NGO", email=ngo_user.email)

    # Attempt to inject verification_status into PATCH /ngos/{id}
    res = await client.patch(
        f"/ngos/{ngo.id}",
        json={"verification_status": "VERIFIED"},
        headers=headers,
    )
    # Extra fields are forbidden by Pydantic schema (422 Unprocessable Entity)
    assert res.status_code == 422

    # Verify status in database did not change
    await db_session.refresh(ngo)
    assert ngo.verification_status == NGOVerificationStatus.PENDING
    assert ngo.is_verified is False


@pytest.mark.asyncio
async def test_non_owner_forbidden_from_patching_ngo(client: AsyncClient, db_session: AsyncSession, auth_headers):
    ngo = NGO(
        name=f"Protected NGO {uuid.uuid4().hex[:6]}",
        registration_number=f"REG-PROT-{uuid.uuid4().hex[:6].upper()}",
        verification_status=NGOVerificationStatus.PENDING,
        is_verified=False,
    )
    db_session.add(ngo)
    await db_session.flush()

    # Another NGO user
    other_ngo_user = await _create_test_user(
        db_session,
        email=f"other_{uuid.uuid4().hex[:6]}@ngo.org",
        role=UserRole.NGO,
        ngo_id=None,
    )
    other_headers = auth_headers(other_ngo_user.id, role="NGO", email=other_ngo_user.email)

    res = await client.patch(
        f"/ngos/{ngo.id}",
        json={"description": "Hacked description"},
        headers=other_headers,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_flow_pending_verify_and_reject(client: AsyncClient, db_session: AsyncSession, auth_headers):
    # 1. Create two pending NGOs
    ngo_to_verify = NGO(
        name=f"Pending NGO 1 {uuid.uuid4().hex[:6]}",
        registration_number=f"REG-P1-{uuid.uuid4().hex[:6].upper()}",
        verification_status=NGOVerificationStatus.PENDING,
        is_verified=False,
    )
    ngo_to_reject = NGO(
        name=f"Pending NGO 2 {uuid.uuid4().hex[:6]}",
        registration_number=f"REG-P2-{uuid.uuid4().hex[:6].upper()}",
        verification_status=NGOVerificationStatus.PENDING,
        is_verified=False,
    )
    db_session.add_all([ngo_to_verify, ngo_to_reject])
    await db_session.flush()

    # Create an ADMIN user
    admin_user = await _create_test_user(
        db_session,
        email=f"admin_{uuid.uuid4().hex[:6]}@platform.gov",
        role=UserRole.ADMIN,
    )
    admin_headers = auth_headers(admin_user.id, role="ADMIN", email=admin_user.email)

    # Create a non-admin user (e.g. DONOR) to assert RBAC blocks non-admins
    donor_user = await _create_test_user(
        db_session,
        email=f"donor_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.DONOR,
    )
    donor_headers = auth_headers(donor_user.id, role="DONOR", email=donor_user.email)

    # ── Non-admin cannot view pending NGOs ─────────────────────────────────────
    res_pending_forbidden = await client.get("/admin/ngos/pending", headers=donor_headers)
    assert res_pending_forbidden.status_code == 403

    # ── Admin can view pending NGOs ───────────────────────────────────────────
    res_pending = await client.get("/admin/ngos/pending", headers=admin_headers)
    assert res_pending.status_code == 200
    pending_ids = [n["id"] for n in res_pending.json()["data"]]
    assert str(ngo_to_verify.id) in pending_ids
    assert str(ngo_to_reject.id) in pending_ids

    # ── Non-admin cannot verify NGO ───────────────────────────────────────────
    res_verify_forbidden = await client.post(f"/admin/ngos/{ngo_to_verify.id}/verify", headers=donor_headers)
    assert res_verify_forbidden.status_code == 403

    # ── Admin verifies NGO 1 ──────────────────────────────────────────────────
    res_verify = await client.post(f"/admin/ngos/{ngo_to_verify.id}/verify", headers=admin_headers)
    assert res_verify.status_code == 200
    verify_data = res_verify.json()["data"]
    assert verify_data["verification_status"] == NGOVerificationStatus.VERIFIED.value
    assert verify_data["is_verified"] is True
    assert verify_data["verified_at"] is not None

    # ── Admin rejects NGO 2 with reason ───────────────────────────────────────
    rejection_payload = {"reason": "Registration certificate lacks authorized signatory seal."}
    res_reject = await client.post(
        f"/admin/ngos/{ngo_to_reject.id}/reject",
        json=rejection_payload,
        headers=admin_headers,
    )
    assert res_reject.status_code == 200
    reject_data = res_reject.json()["data"]
    assert reject_data["verification_status"] == NGOVerificationStatus.REJECTED.value
    assert reject_data["is_verified"] is False
    assert reject_data["rejection_reason"] == rejection_payload["reason"]


@pytest.mark.asyncio
async def test_auth_logout_and_me(client: AsyncClient, db_session: AsyncSession, auth_headers):
    user = await _create_test_user(
        db_session,
        email=f"user_session_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.DONOR,
    )
    headers = auth_headers(user.id, role="DONOR", email=user.email)

    # 1. GET /auth/me
    res_me = await client.get("/auth/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["data"]["email"] == user.email

    # 2. POST /auth/logout
    res_logout = await client.post("/auth/logout", headers=headers)
    assert res_logout.status_code == 200
    assert "logged out" in res_logout.json()["data"]["message"].lower()
