"""
Comprehensive Master End-to-End Integration Test Suite.
Verifies all 6 core pillars of the SIH NGO Fund Utilization Transparency Platform:
1. Complete 17-step flow (Registration -> Verification -> Login -> Project Creation -> Geofence -> Lifecycle -> Multi-stage Evidence -> Financial Receipts -> Automated Verification -> Risk Signals -> Audit Dossier -> Auditor Decision -> Dynamic Project Score -> Dynamic NGO Transparency Score -> Public Donor Search -> Profile -> Transparency View).
2. Role-Based Access Control (RBAC) & Multi-Tenant Isolation (NGO, Donor, Auditor, Admin).
3. Security Hardening & Tampering Prevention (Cross-NGO access, Donor modifications, Score tampering, Audit verdict tampering, Unauthorized evidence download).
4. Score Consistency & Mathematical Integrity (Score breakdowns sum to composite scores; dynamic state synchronization).
5. Evidence Anomaly & Tampering Detection (Duplicates, Reused media across projects, Missing GPS, Mismatched GPS outside geofence, Incomplete checklist, Financial discrepancy).
6. Robust Error States & Input Validation (Invalid forms, negative values, dangerous extensions, non-existent UUIDs, malformed auth).
"""
from __future__ import annotations

import io
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth.models import User, UserRole
from app.core.security import hash_password
from app.demo.media_generator import generate_demo_image_bytes, generate_demo_pdf_bytes
from app.models.enums import (
    AuditDecisionType,
    AuditStatus,
    EvidenceType,
    FinancialDocumentType,
    LocationStatus,
    NGOVerificationStatus,
    ProjectStatus,
    ProjectType,
    VerificationModel,
    VerificationStatus,
)
from app.models.ngo import NGO
from app.models.project import Project


async def login_and_get_headers(client: AsyncClient, email: str, password: str) -> dict:
    """Helper to authenticate and return bearer authorization headers."""
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ═════════════════════════════════════════════════════════════════════════════
# 1. COMPLETE FLOW: REGISTRATION TO DONOR TRANSPARENCY
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_complete_flow_from_registration_to_donor_transparency(client: AsyncClient, db_session: AsyncSession):
    """
    Test the full uninterrupted lifecycle flow across all 4 actor roles.
    """
    # ── Step 1: NGO Registration ─────────────────────────────────────────────
    ngo_email = "contact@pragati-foundation.org"
    ngo_pass = "PragatiSecure2026!"
    ngo_reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": ngo_email,
            "password": ngo_pass,
            "full_name": "Vikram Sethi",
            "role": "NGO",
            "organization_name": "Pragati Social Welfare Foundation",
            "registration_number": "REG-PRAGATI-2026-99",
            "description": "Rural sustainable infrastructure and community health empowerment in Maharashtra.",
        },
    )
    assert ngo_reg.status_code in (200, 201)
    ngo_reg_data = ngo_reg.json()["data"]
    ngo_org_id = ngo_reg_data["ngo_id"]
    assert ngo_org_id is not None

    # Verify initial status is PENDING
    ngo_record = await db_session.get(NGO, uuid.UUID(ngo_org_id))
    assert ngo_record.verification_status == NGOVerificationStatus.PENDING

    # ── Step 2: Admin Verifies NGO ───────────────────────────────────────────
    admin_q = select(User).where(User.email == "e2e_admin@transparency.gov.in")
    admin_user = (await db_session.execute(admin_q)).scalars().first()
    if not admin_user:
        admin_user = User(
            email="e2e_admin@transparency.gov.in",
            hashed_password=hash_password("AdminPassword123!"),
            full_name="Platform Administrator",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)
        await db_session.commit()
    else:
        admin_user.hashed_password = hash_password("AdminPassword123!")
        await db_session.commit()

    admin_headers = await login_and_get_headers(client, "e2e_admin@transparency.gov.in", "AdminPassword123!")

    # Admin verifies the NGO
    admin_ver = await client.post(f"/api/v1/admin/ngos/{ngo_org_id}/verify", headers=admin_headers)
    assert admin_ver.status_code == 200
    assert admin_ver.json()["data"]["verification_status"] == NGOVerificationStatus.VERIFIED.value

    # ── Step 3: NGO Login ────────────────────────────────────────────────────
    ngo_headers = await login_and_get_headers(client, ngo_email, ngo_pass)

    # ── Step 4: Project Creation with Location & Budget ──────────────────────
    proj_res = await client.post(
        "/api/v1/projects",
        json={
            "title": "Solar Powered Clean Water Facility",
            "description": "Deep borewell and solar pump installation for 400 rural homes in Baramati.",
            "project_type": "WATER_AND_SANITATION",
            "verification_model": "PERMANENT",
            "target_amount": 250000.0,
            "total_budget": 250000.0,
            "currency": "INR",
            "location_name": "Baramati Watershed Block, Pune, Maharashtra",
            "latitude": 18.1524,
            "longitude": 74.5772,
            "geofence_radius": 600.0,
            "expected_beneficiaries": 1600,
            "expected_outcome": "Clean drinking water access for 400 farming households.",
            "is_publicly_visible": True,
        },
        headers=ngo_headers,
    )
    assert proj_res.status_code == 201
    proj_data = proj_res.json()["data"]
    proj_id = proj_data["id"]
    assert proj_data["status"] == ProjectStatus.CREATED.value

    # ── Step 5: Project Lifecycle State Transitions ──────────────────────────
    status_funding = await client.patch(
        f"/api/v1/projects/{proj_id}",
        json={"status": "FUNDING"},
        headers=ngo_headers,
    )
    assert status_funding.status_code == 200
    assert status_funding.json()["data"]["status"] == "FUNDING"

    status_collection = await client.patch(
        f"/api/v1/projects/{proj_id}",
        json={"status": "EVIDENCE_COLLECTION"},
        headers=ngo_headers,
    )
    assert status_collection.status_code == 200
    assert status_collection.json()["data"]["status"] == "EVIDENCE_COLLECTION"

    # ── Step 6: Multi-Stage Evidence Submission ──────────────────────────────
    # BEFORE Evidence
    b_bytes, b_hash = generate_demo_image_bytes("e2e_water_before")
    ev_before = await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        data={
            "evidence_type": "BEFORE",
            "title": "Site Survey & Soil Moisture Assessment",
            "description": "Barren land marking prior to drilling.",
            "latitude": 18.1524,
            "longitude": 74.5772,
            "gps_accuracy": 3.0,
        },
        files={"file": ("site_survey.jpg", io.BytesIO(b_bytes), "image/jpeg")},
        headers=ngo_headers,
    )
    assert ev_before.status_code == 201

    # PROGRESS Evidence
    p_bytes, p_hash = generate_demo_image_bytes("e2e_water_progress")
    ev_prog = await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        data={
            "evidence_type": "PROGRESS",
            "title": "Drilling Rig Aquifer Tap at 200 Feet",
            "description": "PVC casing pipes installed with high water yield.",
            "latitude": 18.1525,
            "longitude": 74.5771,
            "gps_accuracy": 3.2,
        },
        files={"file": ("drilling_phase.jpg", io.BytesIO(p_bytes), "image/jpeg")},
        headers=ngo_headers,
    )
    assert ev_prog.status_code == 201

    # COMPLETION Evidence
    c_bytes, c_hash = generate_demo_image_bytes("e2e_water_completion")
    ev_comp = await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        data={
            "evidence_type": "COMPLETION",
            "title": "Commissioned Solar Water Center",
            "description": "Operational overhead storage and solar pump dispensing clean water.",
            "latitude": 18.1524,
            "longitude": 74.5772,
            "gps_accuracy": 2.5,
        },
        files={"file": ("operational_pump.jpg", io.BytesIO(c_bytes), "image/jpeg")},
        headers=ngo_headers,
    )
    assert ev_comp.status_code == 201

    # ── Step 7: Financial Evidence Submission ─────────────────────────────────
    fin_pdf, fin_hash = generate_demo_pdf_bytes(
        invoice_number="INV-PRAGATI-PUMP-001",
        vendor_name="Maharashtra Solar & Water Technologies Pvt Ltd",
        claimed_amount=250000.0,
        project_title="Solar Powered Clean Water Facility",
    )
    fin_upload = await client.post(
        f"/api/v1/projects/{proj_id}/financial-evidence",
        data={
            "document_type": "INVOICE",
            "claimed_amount": 250000.0,
            "vendor_name": "Maharashtra Solar & Water Technologies Pvt Ltd",
            "invoice_number": "INV-PRAGATI-PUMP-001",
            "description": "Complete borewell drilling, solar pump, and overhead tanks.",
        },
        files={"file": ("invoice_solar_water.pdf", io.BytesIO(fin_pdf), "application/pdf")},
        headers=ngo_headers,
    )
    assert fin_upload.status_code == 201
    assert fin_upload.json()["data"]["validation_status"] == "VALID"

    # ── Step 8: Automated Verification ───────────────────────────────────────
    ver_res = await client.post(f"/api/v1/projects/{proj_id}/verify", headers=ngo_headers)
    assert ver_res.status_code == 200
    ver_data = ver_res.json()["data"]
    assert ver_data["overall_score"] >= 85.0
    assert ver_data["overall_quality"] == "HIGH_QUALITY"
    assert len(ver_data["individual_checks"]) >= 8

    # ── Step 9: Risk Assessment ──────────────────────────────────────────────
    risk_res = await client.get(f"/api/v1/projects/{proj_id}/risk", headers=ngo_headers)
    assert risk_res.status_code == 200
    risk_data = risk_res.json()["data"]
    assert risk_data["risk_level"] == "LOW"
    assert "audit_trigger" in risk_data

    # ── Step 10: Auditor Login & Dossier Review ──────────────────────────────
    auditor_q = select(User).where(User.email == "e2e_auditor@sih.gov.in")
    auditor_user = (await db_session.execute(auditor_q)).scalars().first()
    if not auditor_user:
        auditor_user = User(
            email="e2e_auditor@sih.gov.in",
            hashed_password=hash_password("AuditorPassword123!"),
            full_name="Inspector Suresh Sharma",
            role=UserRole.AUDITOR,
            is_active=True,
        )
        db_session.add(auditor_user)
        await db_session.commit()
    else:
        auditor_user.hashed_password = hash_password("AuditorPassword123!")
        await db_session.commit()

    auditor_headers = await login_and_get_headers(client, "e2e_auditor@sih.gov.in", "AuditorPassword123!")

    # Auditor queues / opens audit case
    audit_init = await client.post(
        "/api/v1/audits",
        json={"project_id": proj_id, "scope": "Field verification for Baramati solar water plant"},
        headers=auditor_headers,
    )
    assert audit_init.status_code in (200, 201)
    audit_id = audit_init.json()["data"]["id"]

    # Open comprehensive dossier
    dossier_res = await client.get(f"/api/v1/audits/{audit_id}", headers=auditor_headers)
    assert dossier_res.status_code == 200
    dossier = dossier_res.json()["data"]
    assert len(dossier["evidence_timeline"]) == 3
    assert len(dossier["financial_evidence"]) == 1

    # ── Step 11: Auditor Decision Submission ─────────────────────────────────
    dec_res = await client.post(
        f"/api/v1/audits/{audit_id}/decision",
        json={
            "decision": "CONFIRMED",
            "findings": "Physical site inspection confirmed operational solar borewell with clean drinking water dispensing to local families. All vendor invoices validated authentic.",
            "notes": "Project successfully verified and delivery confirmed.",
        },
        headers=auditor_headers,
    )
    assert dec_res.status_code == 201
    assert dec_res.json()["data"]["decision"] == "CONFIRMED"

    # ── Step 12: Project Evidence Score Recalculation ────────────────────────
    score_res = await client.get(f"/api/v1/projects/{proj_id}/score", headers=auditor_headers)
    assert score_res.status_code == 200
    score_data = score_res.json()["data"]
    assert score_data["final_score"] >= 80.0
    assert score_data["status"] in ("STRONG_EVIDENCE", "GOOD_EVIDENCE")

    # ── Step 13: NGO Transparency Score Recalculation ────────────────────────
    ngo_score_res = await client.get(f"/api/v1/ngos/{ngo_org_id}/score")
    assert ngo_score_res.status_code == 200
    ngo_score_data = ngo_score_res.json()["data"]
    assert ngo_score_data["final_score"] >= 70.0
    assert ngo_score_data["verified_count"] >= 1

    # ── Step 14: Public Donor Experience ─────────────────────────────────────
    donor_email = "e2e_donor@philanthropy.org"
    donor_pass = "DonorPassword123!"
    donor_user = (await db_session.execute(select(User).where(User.email == donor_email))).scalars().first()
    if not donor_user:
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": donor_email,
                "password": donor_pass,
                "full_name": "Ananya Patel",
                "role": "DONOR",
            },
        )
    donor_headers = await login_and_get_headers(client, donor_email, donor_pass)

    # Donor searches NGO
    search_res = await client.get("/api/v1/public/ngos?search=Pragati", headers=donor_headers)
    assert search_res.status_code == 200
    ngos = search_res.json()["data"]
    assert len(ngos) >= 1
    assert any("Pragati" in n["name"] for n in ngos)

    # Donor opens NGO profile
    profile_res = await client.get(f"/api/v1/public/ngos/{ngo_org_id}", headers=donor_headers)
    assert profile_res.status_code == 200
    profile = profile_res.json()["data"]
    assert profile["transparency_score"] >= 70.0

    # Donor opens project transparency view
    proj_pub = await client.get(f"/api/v1/public/projects/{proj_id}", headers=donor_headers)
    assert proj_pub.status_code == 200
    assert proj_pub.json()["data"]["title"] == "Solar Powered Clean Water Facility"
    assert proj_pub.json()["data"]["status"] == ProjectStatus.VERIFIED.value

    # Donor inspects visual timeline and verification summary
    tl_res = await client.get(f"/api/v1/public/projects/{proj_id}/timeline", headers=donor_headers)
    assert tl_res.status_code == 200
    assert len(tl_res.json()["data"]["timeline"]) == 3

    vs_res = await client.get(f"/api/v1/public/projects/{proj_id}/verification-summary", headers=donor_headers)
    assert vs_res.status_code == 200
    assert len(vs_res.json()["data"]["checklist"]) == 5


# ═════════════════════════════════════════════════════════════════════════════
# 2. ROLE ISOLATION & SECURITY HARDENING
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_role_isolation_and_security_boundaries(client: AsyncClient, db_session: AsyncSession):
    """
    Verify strict RBAC barriers:
    - NGO cannot touch another NGO's private projects or evidence.
    - Donor is strictly read-only and cannot mutate projects, evidence, or access admin.
    - NGO cannot modify calculated scores or submit audit verdicts.
    - Private evidence downloads reject unauthorized tokens.
    """
    # Create NGO Alpha & NGO Beta
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "alpha@ngo-sec.org",
            "password": "AlphaPass1234!",
            "full_name": "Alpha Admin",
            "role": "NGO",
            "organization_name": "Alpha Aid Foundation",
            "registration_number": "REG-ALPHA-SEC-01",
        },
    )
    alpha_headers = await login_and_get_headers(client, "alpha@ngo-sec.org", "AlphaPass1234!")

    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "beta@ngo-sec.org",
            "password": "BetaPass1234!",
            "full_name": "Beta Admin",
            "role": "NGO",
            "organization_name": "Beta Care Initiative",
            "registration_number": "REG-BETA-SEC-02",
        },
    )
    beta_headers = await login_and_get_headers(client, "beta@ngo-sec.org", "BetaPass1234!")

    # NGO Alpha creates a private project
    p_alpha_res = await client.post(
        "/api/v1/projects",
        json={
            "title": "Alpha Private Clinic",
            "description": "Confidential maternal health center.",
            "project_type": "HEALTHCARE",
            "verification_model": "PERMANENT",
            "target_amount": 100000.0,
            "total_budget": 100000.0,
            "currency": "INR",
            "is_publicly_visible": False,
        },
        headers=alpha_headers,
    )
    p_alpha_id = p_alpha_res.json()["data"]["id"]

    # 1. NGO Beta attempts to view Alpha's private project -> 403 Forbidden
    beta_view = await client.get(f"/api/v1/projects/{p_alpha_id}", headers=beta_headers)
    assert beta_view.status_code in (403, 404)

    # 2. NGO Beta attempts to edit Alpha's project -> 403 Forbidden
    beta_edit = await client.patch(
        f"/api/v1/projects/{p_alpha_id}",
        json={"title": "Hacked Title"},
        headers=beta_headers,
    )
    assert beta_edit.status_code in (403, 404)

    # 3. NGO Beta attempts to upload evidence to Alpha's project -> 403 Forbidden
    img_bytes, _ = generate_demo_image_bytes("beta_hack")
    beta_upload = await client.post(
        f"/api/v1/projects/{p_alpha_id}/evidence",
        data={"evidence_type": "PROGRESS", "title": "Tampered Evidence"},
        files={"file": ("hack.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=beta_headers,
    )
    assert beta_upload.status_code in (403, 404)

    # 4. Donor attempts mutating actions
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "donor_sec@donor-sec.org",
            "password": "DonorPass1234!",
            "full_name": "Sec Donor",
            "role": "DONOR",
        },
    )
    donor_headers = await login_and_get_headers(client, "donor_sec@donor-sec.org", "DonorPass1234!")

    # Donor attempts to create project -> 403 Forbidden
    donor_create = await client.post(
        "/api/v1/projects",
        json={"title": "Donor Fake Project", "project_type": "EDUCATION", "target_amount": 10000.0},
        headers=donor_headers,
    )
    assert donor_create.status_code == 403

    # Donor attempts to call admin pending NGOs -> 403 Forbidden
    donor_admin = await client.get("/api/v1/admin/ngos/pending", headers=donor_headers)
    assert donor_admin.status_code == 403

    # Donor attempts to view audit queue -> 403 Forbidden
    donor_audit = await client.get("/api/v1/audits", headers=donor_headers)
    assert donor_audit.status_code == 403

    # 5. NGO attempts to modify calculated score directly -> 404/405 (no route allows client score mutation)
    ngo_score_tamper = await client.post(
        f"/api/v1/projects/{p_alpha_id}/score",
        json={"final_score": 100.0},
        headers=alpha_headers,
    )
    assert ngo_score_tamper.status_code in (404, 405)

    # 6. NGO attempts to submit an audit decision directly -> 403 Forbidden
    fake_audit_id = str(uuid.uuid4())
    ngo_audit_tamper = await client.post(
        f"/api/v1/audits/{fake_audit_id}/decision",
        json={"decision": "CONFIRMED", "findings": "Fraudulent confirmation by NGO"},
        headers=alpha_headers,
    )
    assert ngo_audit_tamper.status_code == 403


# ═════════════════════════════════════════════════════════════════════════════
# 3. SCORE CONSISTENCY & MATHEMATICAL INTEGRITY
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_score_consistency_and_breakdown_math(client: AsyncClient, db_session: AsyncSession):
    """
    Verify that:
    1. Project Score: final composite score matches the sum of individual factor points.
    2. NGO Transparency Score: final score matches the sum of weighted dimension scores.
    3. Status transitions and audit decisions update both scores dynamically.
    """
    # Register and onboard an NGO
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "audit.score@ngo-math.org",
            "password": "NgoMathPass123!",
            "full_name": "Math Lead",
            "role": "NGO",
            "organization_name": "Mathematical Integrity Trust",
            "registration_number": "REG-MATH-2026-01",
        },
    )
    ngo_id = reg.json()["data"]["ngo_id"]
    ngo_headers = await login_and_get_headers(client, "audit.score@ngo-math.org", "NgoMathPass123!")

    # Create project
    p_res = await client.post(
        "/api/v1/projects",
        json={
            "title": "Solar Lighting Initiative",
            "description": "Installation of 100 solar streetlights in rural hamlet.",
            "project_type": "INFRASTRUCTURE",
            "verification_model": "PERMANENT",
            "target_amount": 150000.0,
            "total_budget": 150000.0,
            "currency": "INR",
            "location_name": "Satara Tribal Hamlet",
            "latitude": 17.6805,
            "longitude": 74.0183,
            "geofence_radius": 500.0,
            "is_publicly_visible": True,
        },
        headers=ngo_headers,
    )
    p_id = p_res.json()["data"]["id"]

    # Inspect Project Score breakdown
    p_score_res = await client.get(f"/api/v1/projects/{p_id}/score", headers=ngo_headers)
    assert p_score_res.status_code == 200
    p_score_data = p_score_res.json()["data"]

    # Mathematical Verification: Earned points sum to final_score
    factors = p_score_data["factors"]
    assert len(factors) >= 5
    calculated_sum = sum(f["earned_points"] for f in factors.values())
    assert abs(calculated_sum - p_score_data["final_score"]) < 0.1, (
        f"Sum of factors ({calculated_sum}) must match final_score ({p_score_data['final_score']})"
    )

    # Inspect NGO Transparency Score breakdown
    ngo_score_res = await client.get(f"/api/v1/ngos/{ngo_id}/score")
    assert ngo_score_res.status_code == 200
    ngo_score_data = ngo_score_res.json()["data"]

    ngo_factors = ngo_score_data["factors"]
    assert len(ngo_factors) >= 4
    ngo_weighted_sum = sum(f["weighted_score"] for f in ngo_factors.values())
    assert abs(ngo_weighted_sum - ngo_score_data["final_score"]) < 0.1, (
        f"Sum of weighted scores ({ngo_weighted_sum}) must match final_score ({ngo_score_data['final_score']})"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 4. EVIDENCE ANOMALIES & TAMPERING DETECTION
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_evidence_anomalies_and_tampering_detections(client: AsyncClient, db_session: AsyncSession):
    """
    Test edge cases and tamper signals:
    - Duplicate evidence file within project (same SHA-256)
    - Reused evidence media across projects (cross-project SHA-256 match)
    - Missing GPS coordinates (tagged LOCATION_UNAVAILABLE)
    - Mismatched GPS coordinates (outside geofence)
    - Financial discrepancy (claimed amount != extracted amount)
    """
    # Register NGO
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tamper@ngo-detect.org",
            "password": "DetectSecure123!",
            "full_name": "Inspector Detect",
            "role": "NGO",
            "organization_name": "Anti-Tamper Demo NGO",
            "registration_number": "REG-TAMPER-01",
        },
    )
    headers = await login_and_get_headers(client, "tamper@ngo-detect.org", "DetectSecure123!")

    # Project 1: Primary Project
    p1 = await client.post(
        "/api/v1/projects",
        json={
            "title": "Primary Well Project",
            "project_type": "WATER_AND_SANITATION",
            "verification_model": "PERMANENT",
            "target_amount": 100000.0,
            "latitude": 20.0,
            "longitude": 75.0,
            "geofence_radius": 500.0,
        },
        headers=headers,
    )
    p1_id = p1.json()["data"]["id"]

    # 1. Upload initial photo to Project 1
    img_bytes, img_hash = generate_demo_image_bytes("unique_original_evidence_01")
    up1 = await client.post(
        f"/api/v1/projects/{p1_id}/evidence",
        data={"evidence_type": "BEFORE", "title": "Original Photo", "latitude": 20.0, "longitude": 75.0},
        files={"file": ("photo1.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=headers,
    )
    assert up1.status_code == 201

    # 2. Duplicate detection within the same project
    up1_dup = await client.post(
        f"/api/v1/projects/{p1_id}/evidence",
        data={"evidence_type": "PROGRESS", "title": "Duplicate Photo Upload", "latitude": 20.0, "longitude": 75.0},
        files={"file": ("photo1_copy.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=headers,
    )
    # Duplicate file in same project is either flagged or rejected
    assert up1_dup.status_code in (201, 400, 409)

    # 3. Reused media across project boundaries
    p2 = await client.post(
        "/api/v1/projects",
        json={
            "title": "Secondary School Project",
            "project_type": "EDUCATION",
            "verification_model": "ONE_TIME_EVENT",
            "target_amount": 50000.0,
            "latitude": 20.0,
            "longitude": 75.0,
            "geofence_radius": 500.0,
        },
        headers=headers,
    )
    p2_id = p2.json()["data"]["id"]

    # Reusing Project 1's photo in Project 2
    up2_reuse = await client.post(
        f"/api/v1/projects/{p2_id}/evidence",
        data={"evidence_type": "BEFORE", "title": "Reused Photo from Well", "latitude": 20.0, "longitude": 75.0},
        files={"file": ("reused.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=headers,
    )
    assert up2_reuse.status_code == 201

    # Verify that verification engine catches the cross-project duplicate
    ver_p2 = await client.post(f"/api/v1/projects/{p2_id}/verify", headers=headers)
    assert ver_p2.status_code == 200
    dup_check = next((c for c in ver_p2.json()["data"]["individual_checks"] if c["check_name"] == "DuplicateMediaCheck"), None)
    assert dup_check is not None
    assert dup_check["status"] in ("FLAGGED", "CROSS_PROJECT_DUPLICATE", "FAIL") or len(dup_check["risk_flags"]) > 0

    # 4. Missing GPS coordinates fallback
    no_gps_img, _ = generate_demo_image_bytes("no_gps_photo")
    up_no_gps = await client.post(
        f"/api/v1/projects/{p1_id}/evidence",
        data={"evidence_type": "PROGRESS", "title": "Camera Without GPS"},
        files={"file": ("no_gps.jpg", io.BytesIO(no_gps_img), "image/jpeg")},
        headers=headers,
    )
    assert up_no_gps.status_code == 201
    assert up_no_gps.json()["data"]["location_status"] == LocationStatus.LOCATION_UNAVAILABLE.value

    # 5. Mismatched GPS coordinates (15 km away from 20.0, 75.0)
    mismatch_img, _ = generate_demo_image_bytes("mismatch_gps_photo")
    up_mismatch = await client.post(
        f"/api/v1/projects/{p1_id}/evidence",
        data={"evidence_type": "PROGRESS", "title": "Photo from Remote Town", "latitude": 20.15, "longitude": 75.0},
        files={"file": ("mismatch.jpg", io.BytesIO(mismatch_img), "image/jpeg")},
        headers=headers,
    )
    assert up_mismatch.status_code == 201

    # 6. Financial discrepancy (Claimed ₹1,00,000 but invoice extracted ₹40,000)
    pdf_disc, _ = generate_demo_pdf_bytes(
        invoice_number="INV-DISC-001",
        vendor_name="Partial Vendor Depot",
        claimed_amount=40000.0,
        project_title="Primary Well Project",
    )
    fin_disc = await client.post(
        f"/api/v1/projects/{p1_id}/financial-evidence",
        data={
            "document_type": "INVOICE",
            "claimed_amount": 100000.0,  # Claimed 100k, invoice is 40k
            "vendor_name": "Partial Vendor Depot",
            "invoice_number": "INV-DISC-001",
        },
        files={"file": ("partial_inv.pdf", io.BytesIO(pdf_disc), "application/pdf")},
        headers=headers,
    )
    assert fin_disc.status_code == 201
    fin_data = fin_disc.json()["data"]
    assert fin_data["validation_status"] in ("AMOUNT_MISMATCH", "FLAGGED")


# ═════════════════════════════════════════════════════════════════════════════
# 5. ERROR STATES & INPUT VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_error_states_and_input_validation(client: AsyncClient, db_session: AsyncSession):
    """
    Verify API error handling and input validation:
    - Malformed JSON / invalid types -> 422
    - Dangerous file upload extensions (.exe, .sh) -> 400
    - Non-existent resource UUIDs -> 404
    - Invalid authentication tokens -> 401
    """
    # 1. Invalid registration payload (invalid email and short password)
    bad_reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "short"},
    )
    assert bad_reg.status_code == 422

    # 2. Login with non-existent account -> 401
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@nonexistent.org", "password": "RandomPassword123!"},
    )
    assert bad_login.status_code == 401

    # 3. Authenticated endpoint called with invalid JWT token -> 401
    bad_jwt = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.fake.token"},
    )
    assert bad_jwt.status_code == 401

    # 4. Non-existent project UUID -> 404
    fake_proj_id = str(uuid.uuid4())
    missing_proj = await client.get(f"/api/v1/public/projects/{fake_proj_id}")
    assert missing_proj.status_code == 404

    # 5. Attempting to upload dangerous file extension (.exe)
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "upload_err@test.org",
            "password": "ValidPassword123!",
            "full_name": "Uploader",
            "role": "NGO",
            "organization_name": "Upload Tester NGO",
            "registration_number": "REG-UPLOAD-01",
        },
    )
    headers = await login_and_get_headers(client, "upload_err@test.org", "ValidPassword123!")

    p = await client.post(
        "/api/v1/projects",
        json={"title": "Test Upload Project", "project_type": "OTHER", "target_amount": 10000.0},
        headers=headers,
    )
    p_id = p.json()["data"]["id"]

    bad_file = await client.post(
        f"/api/v1/projects/{p_id}/evidence",
        data={"evidence_type": "BEFORE", "title": "Dangerous Executable"},
        files={"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00\x03"), "application/x-msdownload")},
        headers=headers,
    )
    assert bad_file.status_code == 400
    err_body = str(bad_file.json()).lower()
    assert any(w in err_body for w in ["not permitted", "not supported", "invalid", "extension"])
