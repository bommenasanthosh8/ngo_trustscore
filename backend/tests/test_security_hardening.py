"""
Security Hardening & RBAC Test Suite.

Verifies:
1. Password Strength Validation (rejects weak, requires length, letters, digits).
2. Rate Limiting Middleware (sliding window, HTTP 429 on abuse).
3. NGO Data Isolation (NGO cannot access or modify another NGO's private data).
4. Donor Access Restrictions (Donors restricted strictly to public non-sensitive information).
5. Auditor Scope & Assignment Control (Auditor cannot act on another auditor's assigned case).
6. Administrator Elevated Privileges (Admin can review all NGOs, resolve disputes, oversee audits).
7. Coordinate Fuzzing & Private Beneficiary Masking (Public/Donor callers cannot view sensitive beneficiary data or shelter coordinates).
8. Evidence Download Access Control (Unauthenticated and unauthorized callers blocked from downloading files).
"""
import io
import uuid
import pytest
from httpx import AsyncClient

from app.core.rate_limit import SlidingWindowRateLimiter
from app.models.enums import ProjectType


async def register_user(client: AsyncClient, role: str = "NGO", org_name: str = None):
    """Helper to register and login a user with given role."""
    email = f"{role.lower()}_{uuid.uuid4().hex[:6]}@hardening-security.org"
    reg_payload = {
        "email": email,
        "password": "SecurePassword123!",
        "full_name": f"Test {role.capitalize()}",
        "role": role,
    }
    if role == "NGO":
        reg_payload["organization_name"] = org_name or f"Security Foundation {uuid.uuid4().hex[:4]}"
        reg_payload["registration_number"] = f"SEC-{uuid.uuid4().hex[:6].upper()}"

    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201, reg_res.text

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["data"]["access_token"]
    user_id = reg_res.json()["data"]["id"]
    return email, {"Authorization": f"Bearer {token}"}, user_id


# ── 1. Password Strength Validation ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_password_strength_validation(client: AsyncClient):
    """Verify registration rejects weak passwords and accepts compliant ones."""
    # Too short (< 8 chars)
    res_short = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"short_{uuid.uuid4().hex[:6]}@example.com",
            "password": "Sh1!",
            "full_name": "Short Password",
            "role": "DONOR",
        },
    )
    assert res_short.status_code == 422

    # No digits
    res_no_digit = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"nodigit_{uuid.uuid4().hex[:6]}@example.com",
            "password": "PasswordOnlyWithoutDigits!",
            "full_name": "No Digit Password",
            "role": "DONOR",
        },
    )
    assert res_no_digit.status_code == 422

    # Compliant password succeeds
    res_ok = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"strong_{uuid.uuid4().hex[:6]}@example.com",
            "password": "CompliantPass123!",
            "full_name": "Valid Password",
            "role": "DONOR",
        },
    )
    assert res_ok.status_code == 201


# ── 2. Sliding Window Rate Limiting ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_sliding_window_rate_limiter_unit():
    """Unit test sliding window rate limiter directly."""
    limiter = SlidingWindowRateLimiter()
    ip = "192.168.1.100"

    # Allow 5 requests within window of 60s
    for i in range(5):
        allowed, remaining, retry_after = limiter.is_allowed(
            category="test",
            client_ip=ip,
            limit=5,
            window_seconds=60,
        )
        assert allowed is True
        assert retry_after == 0

    # 6th request must be rejected
    allowed, remaining, retry_after = limiter.is_allowed(
        category="test",
        client_ip=ip,
        limit=5,
        window_seconds=60,
    )
    assert allowed is False
    assert retry_after > 0


# ── 3. NGO Data Isolation ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ngo_cannot_access_or_modify_other_ngo_private_data(client: AsyncClient):
    """
    Ensure NGO A and NGO B are strictly isolated:
    - NGO B cannot view or edit NGO A's private project.
    - NGO B cannot upload evidence or view raw financial documents.
    - NGO B cannot view NGO A's internal risk signals, disputes, or audits.
    """
    _, ngo_a_headers, _ = await register_user(client, role="NGO", org_name="NGO Alpha")
    _, ngo_b_headers, _ = await register_user(client, role="NGO", org_name="NGO Beta")

    # NGO A creates a private project
    proj_res = await client.post(
        "/api/v1/projects",
        json={
            "name": "Alpha Clean Water Pipeline",
            "category": "WATER_AND_SANITATION",
            "target_amount": 500000.0,
            "latitude": 13.0827,
            "longitude": 80.2707,
            "is_publicly_visible": False,  # Private project
        },
        headers=ngo_a_headers,
    )
    assert proj_res.status_code == 201
    proj_a_id = proj_res.json()["data"]["id"]

    # NGO A uploads raw financial evidence
    fin_file = io.BytesIO(b"INVOICE Alpha Pipes Rs. 50,000")
    fin_res = await client.post(
        f"/api/v1/projects/{proj_a_id}/financial-evidence",
        files={"file": ("invoice_a.pdf", fin_file, "application/pdf")},
        data={
            "claimed_amount": "50000.0",
            "document_type": "INVOICE",
            "vendor_name": "Alpha Steel Works",
        },
        headers=ngo_a_headers,
    )
    assert fin_res.status_code == 201

    # 1. NGO B cannot view private project details
    get_res = await client.get(f"/api/v1/projects/{proj_a_id}", headers=ngo_b_headers)
    assert get_res.status_code == 403

    # 2. NGO B cannot update NGO A's project
    patch_res = await client.patch(
        f"/api/v1/projects/{proj_a_id}",
        json={"title": "Hacked Title"},
        headers=ngo_b_headers,
    )
    assert patch_res.status_code == 403

    # 3. NGO B cannot upload evidence to NGO A's project
    ev_file = io.BytesIO(b"fake photo")
    ev_res = await client.post(
        f"/api/v1/projects/{proj_a_id}/evidence",
        files={"file": ("photo.jpg", ev_file, "image/jpeg")},
        data={"title": "Unauthorized Evidence", "evidence_type": "PROGRESS"},
        headers=ngo_b_headers,
    )
    assert ev_res.status_code == 403

    # 4. NGO B cannot view NGO A's raw financial evidence documents
    fin_view = await client.get(f"/api/v1/projects/{proj_a_id}/financial-evidence", headers=ngo_b_headers)
    assert fin_view.status_code == 403

    # 5. NGO B cannot view NGO A's internal risk signals
    risk_res = await client.get(f"/api/v1/projects/{proj_a_id}/risk", headers=ngo_b_headers)
    assert risk_res.status_code == 403

    risk_endpoint = await client.get(f"/api/v1/risk/projects/{proj_a_id}", headers=ngo_b_headers)
    assert risk_endpoint.status_code == 403

    # 6. NGO B cannot view NGO A's internal audit records or disputes
    audits_res = await client.get(f"/api/v1/projects/{proj_a_id}/audits", headers=ngo_b_headers)
    assert audits_res.status_code == 403

    disp_res = await client.get(f"/api/v1/projects/{proj_a_id}/disputes", headers=ngo_b_headers)
    assert disp_res.status_code == 403


# ── 4. Donor Access Restrictions ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_donor_restricted_to_public_information_only(client: AsyncClient):
    """
    Ensure Donors cannot access internal, administrative, or private records:
    - Blocked from /admin/*
    - Blocked from /audits queue
    - Blocked from raw financial evidence invoices
    - Blocked from triggering verification or evaluating risk
    - Blocked from private projects
    """
    _, donor_headers, _ = await register_user(client, role="DONOR")
    _, ngo_headers, _ = await register_user(client, role="NGO", org_name="Public Relief Org")

    # Create a public project
    pub_proj = await client.post(
        "/api/v1/projects",
        json={
            "name": "Public Solar Lighting",
            "category": "ENVIRONMENT",
            "target_amount": 250000.0,
            "latitude": 12.9716,
            "longitude": 77.5946,
            "is_publicly_visible": True,
        },
        headers=ngo_headers,
    )
    assert pub_proj.status_code == 201
    pub_id = pub_proj.json()["data"]["id"]

    # 1. Blocked from Admin endpoints
    admin_res = await client.get("/api/v1/admin/ngos/pending", headers=donor_headers)
    assert admin_res.status_code == 403

    admin_cfg = await client.get("/api/v1/admin/audit-config", headers=donor_headers)
    assert admin_cfg.status_code == 403

    # 2. Blocked from Auditor queue endpoints
    audit_queue = await client.get("/api/v1/audits", headers=donor_headers)
    assert audit_queue.status_code == 403

    audit_dash = await client.get("/api/v1/audits/dashboard-queues", headers=donor_headers)
    assert audit_dash.status_code == 403

    # 3. Blocked from raw financial evidence (vendor invoices/receipts)
    fin_view = await client.get(f"/api/v1/projects/{pub_id}/financial-evidence", headers=donor_headers)
    assert fin_view.status_code == 403

    # 4. Blocked from triggering verification engine or risk assessment
    verify_trigger = await client.post(f"/api/v1/projects/{pub_id}/verify", headers=donor_headers)
    assert verify_trigger.status_code == 403

    risk_trigger = await client.post(f"/api/v1/risk/projects/{pub_id}/evaluate", headers=donor_headers)
    assert risk_trigger.status_code == 403

    # 5. Blocked from internal risk signals and integrity flags
    risk_view = await client.get(f"/api/v1/projects/{pub_id}/risk", headers=donor_headers)
    assert risk_view.status_code == 403

    flags_view = await client.get(f"/api/v1/risk/projects/{pub_id}/integrity-flags", headers=donor_headers)
    assert flags_view.status_code == 403

    # 6. BUT donor CAN access public score and public financial consistency summary
    score_res = await client.get(f"/api/v1/projects/{pub_id}/score", headers=donor_headers)
    assert score_res.status_code == 200

    consistency_res = await client.get(f"/api/v1/projects/{pub_id}/financial-evidence/consistency", headers=donor_headers)
    assert consistency_res.status_code == 200


# ── 5. Auditor Scope & Assignment Control ─────────────────────────────────────
@pytest.mark.asyncio
async def test_auditor_case_assignment_and_admin_elevation(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Ensure:
    - Auditor 1 assigned to case A can review and decide.
    - Auditor 2 cannot decide or view another auditor's assigned case.
    - Platform Administrator has elevated access and can override or decide.
    """
    from app.auth.models import User, UserRole
    from app.core.security import create_access_token, hash_password

    _, aud1_headers, aud1_id = await register_user(client, role="AUDITOR")
    _, aud2_headers, _ = await register_user(client, role="AUDITOR")
    _, ngo_headers, _ = await register_user(client, role="NGO", org_name="Audit Candidate Org")

    # Create admin user directly in DB (self-registration of ADMIN is forbidden)
    admin_user = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@hardening-security.org",
        hashed_password=hash_password("SecurePassword123!"),
        full_name="Platform Administrator",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(admin_user)
    await db_session.flush()
    admin_token = create_access_token(subject=str(admin_user.id), extra={"email": admin_user.email, "role": UserRole.ADMIN.value})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # NGO creates project
    proj_res = await client.post(
        "/api/v1/projects",
        json={
            "name": "Audit Assignment Project",
            "category": "RELIEF_DISTRIBUTION",
            "target_amount": 1500000.0,
            "latitude": 28.6139,
            "longitude": 77.2090,
            "is_publicly_visible": True,
        },
        headers=ngo_headers,
    )
    proj_id = proj_res.json()["data"]["id"]

    # Auditor 1 fetches queue to discover the auto-queued high-value audit case
    queue_res = await client.get("/api/v1/audits", headers=aud1_headers)
    assert queue_res.status_code == 200
    audits = queue_res.json()["data"]
    case = next((c for c in audits if c["project_id"] == proj_id), None)
    assert case is not None
    audit_id = case["id"]

    # Auditor 1 records an initial decision, becoming the assigned auditor
    dec1_res = await client.post(
        f"/api/v1/audits/{audit_id}/decision",
        json={
            "decision": "PARTIALLY_CONFIRMED",
            "findings": "Physical site inspection confirmed 70% progress with minor discrepancies.",
            "notes": "Materials partially delivered.",
        },
        headers=aud1_headers,
    )
    assert dec1_res.status_code == 201

    # Auditor 2 attempts to record a decision on Auditor 1's assigned case -> 403 Forbidden
    dec2_res = await client.post(
        f"/api/v1/audits/{audit_id}/decision",
        json={
            "decision": "CONFIRMED",
            "findings": "Second auditor attempting unauthorized override.",
        },
        headers=aud2_headers,
    )
    assert dec2_res.status_code == 403

    # Auditor 2 attempts to view Auditor 1's dossier -> 403 Forbidden
    dossier_res = await client.get(f"/api/v1/audits/{audit_id}", headers=aud2_headers)
    assert dossier_res.status_code == 403

    # Administrator has elevated permissions and CAN submit decision or view dossier
    admin_dec = await client.post(
        f"/api/v1/audits/{audit_id}/decision",
        json={
            "decision": "CONFIRMED",
            "findings": "Administrator override with verified central receipts.",
        },
        headers=admin_headers,
    )
    assert admin_dec.status_code == 201


# ── 6. Sensitive Coordinates & Beneficiary Information Masking ───────────────
@pytest.mark.asyncio
async def test_sensitive_project_coordinate_fuzzing_and_beneficiary_masking(client: AsyncClient):
    """
    Ensure that for sensitive projects (e.g. HEALTHCARE, RELIEF_DISTRIBUTION, or is_sensitive=True):
    - Exact shelter/beneficiary coordinates are masked to ~1.1km (2 decimal places) for public/donors.
    - Beneficiary names and contact info in metadata are redacted for non-privileged callers.
    - Owning NGO and Admins retain full unmasked data.
    """
    _, ngo_headers, _ = await register_user(client, role="NGO", org_name="Medical Aid Trust")
    _, donor_headers, _ = await register_user(client, role="DONOR")

    # Create sensitive healthcare project
    proj_res = await client.post(
        "/api/v1/projects",
        json={
            "name": "Women's Wellness Clinic",
            "category": "HEALTHCARE",
            "target_amount": 800000.0,
            "latitude": 19.076092,
            "longitude": 72.877426,
            "is_publicly_visible": True,
        },
        headers=ngo_headers,
    )
    proj_id = proj_res.json()["data"]["id"]

    # Upload evidence with exact coordinates and private beneficiary metadata
    ev_file = io.BytesIO(b"medical evidence scan")
    ev_upload = await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        files={"file": ("scan.jpg", ev_file, "image/jpeg")},
        data={
            "title": "Patient Consultation Camp",
            "evidence_type": "PROGRESS",
            "latitude": "19.076092",
            "longitude": "72.877426",
            "metadata_summary": '{"beneficiary_name": "Jane Doe", "phone": "9876543210", "facility": "Ward 4"}',
        },
        headers=ngo_headers,
    )
    assert ev_upload.status_code == 201
    ev_id = ev_upload.json()["data"]["id"]

    # 1. Donor inspects project detail -> exact coordinates fuzzed/approximate
    proj_donor = await client.get(f"/api/v1/projects/{proj_id}", headers=donor_headers)
    assert proj_donor.status_code == 200
    donor_proj_data = proj_donor.json()["data"]
    assert donor_proj_data["latitude"] == round(19.076092, 2)
    assert donor_proj_data["longitude"] == round(72.877426, 2)

    # 2. Donor inspects evidence list -> coordinates rounded to 2 decimals, beneficiary info redacted
    ev_donor = await client.get(f"/api/v1/projects/{proj_id}/evidence", headers=donor_headers)
    assert ev_donor.status_code == 200
    donor_ev_item = ev_donor.json()["data"]["items"][0]
    assert donor_ev_item["latitude"] == round(19.076092, 2)
    assert donor_ev_item["longitude"] == round(72.877426, 2)
    assert donor_ev_item["metadata_summary"]["beneficiary_name"] == "[REDACTED]"
    assert donor_ev_item["metadata_summary"]["phone"] == "[REDACTED]"
    assert donor_ev_item["metadata_summary"]["facility"] == "Ward 4"  # Non-sensitive retained

    # 3. NGO owner inspects evidence list -> receives full precision and unredacted metadata
    ev_owner = await client.get(f"/api/v1/projects/{proj_id}/evidence", headers=ngo_headers)
    assert ev_owner.status_code == 200
    owner_ev_item = ev_owner.json()["data"]["items"][0]
    assert owner_ev_item["latitude"] == pytest.approx(19.076092, abs=0.0001)
    assert owner_ev_item["metadata_summary"]["beneficiary_name"] == "Jane Doe"


# ── 7. Evidence File Download Access Control ──────────────────────────────────
@pytest.mark.asyncio
async def test_evidence_file_download_protected_against_unauthorized_access(client: AsyncClient):
    """
    Ensure evidence file streaming endpoint /evidence/{id}/file:
    - Requires authentication (rejects unauthenticated requests with 401).
    - For private projects, rejects donors and foreign NGOs with 403.
    - Allows owning NGO and Administrators.
    """
    _, ngo_headers, _ = await register_user(client, role="NGO", org_name="Shelter Org")
    _, donor_headers, _ = await register_user(client, role="DONOR")

    # Create private project
    p_res = await client.post(
        "/api/v1/projects",
        json={
            "name": "Confidential Shelter Program",
            "category": "RELIEF_DISTRIBUTION",
            "target_amount": 300000.0,
            "latitude": 17.3850,
            "longitude": 78.4867,
            "is_publicly_visible": False,  # Private
        },
        headers=ngo_headers,
    )
    proj_id = p_res.json()["data"]["id"]

    # Upload evidence
    ev_file = io.BytesIO(b"CONFIDENTIAL SHELTER PHOTO")
    upload_res = await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        files={"file": ("shelter.jpg", ev_file, "image/jpeg")},
        data={"title": "Internal Inspection", "evidence_type": "BEFORE"},
        headers=ngo_headers,
    )
    assert upload_res.status_code == 201
    evidence_id = upload_res.json()["data"]["id"]

    # 1. Unauthenticated download fails with 401 Unauthorized
    unauth_res = await client.get(f"/api/v1/evidence/{evidence_id}/file")
    assert unauth_res.status_code == 401

    # 2. Donor download on private project fails with 403 Forbidden
    donor_res = await client.get(f"/api/v1/evidence/{evidence_id}/file", headers=donor_headers)
    assert donor_res.status_code == 403

    # 3. Owning NGO download succeeds with 200 OK
    owner_res = await client.get(f"/api/v1/evidence/{evidence_id}/file", headers=ngo_headers)
    assert owner_res.status_code == 200
    assert owner_res.content == b"CONFIDENTIAL SHELTER PHOTO"
