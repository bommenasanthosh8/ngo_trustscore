"""
End-to-End Automated Test for the Complete 23-Step SIH Demonstration Flow.

Verifies:
1. Full seeding of the fictional SIH dataset (Scenarios A, B, C, D).
2. The complete 23-step demonstration workflow from NGO creation to Donor transparency inspection:
   - Steps 1-4: NGO Login & Project Creation with Map Location & Budget
   - Steps 5-8: Multi-Stage Evidence & Financial Invoice Uploads
   - Steps 9-12: 10-Point Verification Engine, Risk Signals, & Audit Trigger
   - Steps 13-17: Independent Auditor Login, Dossier Review, CONFIRMED Decision, & Dynamic Recalculation
   - Steps 18-23: Donor Experience, NGO Search, Profile, Historical Trend, Timeline, & Score Transparency
"""
from __future__ import annotations

import io
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.demo.service import seed_sih_demonstration_data
from app.models.enums import ProjectStatus, ProjectType


@pytest.mark.asyncio
async def test_sih_demonstration_dataset_scenarios(client: AsyncClient, db_session: AsyncSession):
    """
    Verify that the demonstration dataset populates all 4 required scenarios:
    - Scenario A: Strong project (Water Well, 88/100, LOW risk, VERIFIED)
    - Scenario B: Medium project (Book Distribution, 72/100, MEDIUM risk, PARTIALLY_VERIFIED)
    - Scenario C: Suspicious project (Medical Camp, 41/100, HIGH risk, DISPUTED, location mismatch & fraud)
    - Scenario D: Pending project (Food Distribution, incomplete evidence, PENDING)
    - Historical score trends for NGOs and projects.
    """
    # 1. Seed dataset via service
    summary = await seed_sih_demonstration_data(db_session)
    assert summary["status"] == "SUCCESS"
    assert len(summary["ngos"]) == 2
    assert len(summary["projects"]) == 6

    # 2. Verify Scenario A: Community Water Well
    res_a = await client.get("/api/v1/projects/NGO-WELL-2026-0001")
    assert res_a.status_code == 200
    data_a = res_a.json()["data"]
    assert data_a["status"] == ProjectStatus.VERIFIED.value
    assert float(data_a["evidence_score"]) == 88.0
    assert data_a["target_amount"] == 200000.0

    # 3. Verify Scenario B: School Book Distribution
    res_b = await client.get("/api/v1/projects/NGO-EDU-2026-0001")
    assert res_b.status_code == 200
    data_b = res_b.json()["data"]
    assert data_b["status"] == ProjectStatus.PARTIALLY_VERIFIED.value
    assert float(data_b["evidence_score"]) == 72.0
    assert data_b["target_amount"] == 75000.0

    # 4. Verify Scenario C: Medical Camp (Suspicious & Disputed)
    res_c = await client.get("/api/v1/projects/NGO-HLTH-2026-0001")
    assert res_c.status_code == 200
    data_c = res_c.json()["data"]
    assert data_c["status"] == ProjectStatus.DISPUTED.value
    assert float(data_c["evidence_score"]) == 41.0
    assert data_c["target_amount"] == 120000.0

    # 5. Verify Scenario D: Community Food Distribution (Pending)
    res_d = await client.get("/api/v1/projects/NGO-FOOD-2026-0001")
    assert res_d.status_code == 200
    data_d = res_d.json()["data"]
    assert data_d["status"] in (ProjectStatus.PENDING.value, ProjectStatus.EVIDENCE_COLLECTION.value)
    assert data_d["target_amount"] == 50000.0

    # 6. Verify Personas Endpoint
    personas_res = await client.get("/api/v1/demo/personas")
    assert personas_res.status_code == 200
    assert len(personas_res.json()["data"]) == 5


@pytest.mark.asyncio
async def test_complete_23_step_sih_demo_workflow(client: AsyncClient, db_session: AsyncSession):
    """
    Executes the exact 23-step SIH demonstration workflow programmatically.
    Ensures that a presenter or judge can run the entire lifecycle from start to finish
    without any manual database manipulation.
    """
    # Initialize base demo data
    await seed_sih_demonstration_data(db_session)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: Login as NGO (Ramesh Verma, Helping Villages Foundation)
    # ─────────────────────────────────────────────────────────────────────────
    ngo_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "lead@helpingvillages.org", "password": "NgoPassword123!"},
    )
    assert ngo_login.status_code == 200
    ngo_token = ngo_login.json()["data"]["access_token"]
    ngo_headers = {"Authorization": f"Bearer {ngo_token}"}

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2-4: Create "Community Water Well - Live Demo", Pick Map Location & Budget
    # ─────────────────────────────────────────────────────────────────────────
    create_proj_res = await client.post(
        "/api/v1/projects",
        json={
            "name": "Community Water Well - Live Demo",
            "category": "WATER_AND_SANITATION",
            "description": "Solar-powered community borewell supplying potable water to 350 rural families.",
            "target_amount": 200000.0,
            "expected_beneficiaries": 1200,
            "location": {
                "location_name": "Rampur Village Site, Varanasi, UP",
                "latitude": 25.3176,
                "longitude": 82.9739,
                "geofence_radius": 500.0,
            },
            "is_publicly_visible": True,
        },
        headers=ngo_headers,
    )
    assert create_proj_res.status_code == 201
    proj = create_proj_res.json()["data"]
    proj_id = proj["id"]
    assert proj["target_amount"] == 200000.0
    assert proj["latitude"] == 25.3176
    assert proj["longitude"] == 82.9739

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5: Submit BEFORE evidence
    # ─────────────────────────────────────────────────────────────────────────
    before_img = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIFbefore_water_well")
    ev_before = await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        files={"file": ("survey_before.jpg", before_img, "image/jpeg")},
        data={
            "title": "Initial Arid Ground Site Inspection",
            "evidence_type": "BEFORE",
            "latitude": "25.3176",
            "longitude": "82.9739",
            "description": "Pre-construction arid survey before drilling.",
        },
        headers=ngo_headers,
    )
    assert ev_before.status_code == 201

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6: Submit PROGRESS evidence
    # ─────────────────────────────────────────────────────────────────────────
    progress_img = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIFprogress_drilling")
    ev_progress = await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        files={"file": ("drilling_progress.jpg", progress_img, "image/jpeg")},
        data={
            "title": "Borewell Rig Deep Drilling at 180 Feet",
            "evidence_type": "PROGRESS",
            "latitude": "25.3177",
            "longitude": "82.9738",
            "description": "Drilling casing pipe installation in progress.",
        },
        headers=ngo_headers,
    )
    assert ev_progress.status_code == 201

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 7: Submit COMPLETION evidence
    # ─────────────────────────────────────────────────────────────────────────
    completion_img = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIFcompletion_flowing_water")
    ev_completion = await client.post(
        f"/api/v1/projects/{proj_id}/evidence",
        files={"file": ("completed_borewell.jpg", completion_img, "image/jpeg")},
        data={
            "title": "Operational Solar Water Pump Flowing Clean Water",
            "evidence_type": "COMPLETION",
            "latitude": "25.3176",
            "longitude": "82.9739",
            "description": "Potable water flowing from operational solar pump.",
        },
        headers=ngo_headers,
    )
    assert ev_completion.status_code == 201

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 8: Submit Financial Evidence
    # ─────────────────────────────────────────────────────────────────────────
    invoice_pdf = io.BytesIO(b"%PDF-1.4\nInvoice No: INV-KASHI-DEMO-991\nAmount: INR 200,000\n%%EOF")
    fin_upload = await client.post(
        f"/api/v1/projects/{proj_id}/financial-evidence",
        files={"file": ("borewell_invoice.pdf", invoice_pdf, "application/pdf")},
        data={
            "claimed_amount": "200000.0",
            "document_type": "INVOICE",
            "vendor_name": "Kashi Borewell & Solar Equipment Ltd",
            "invoice_number": "INV-KASHI-DEMO-991",
            "description": "Solar pump, drilling rig hire, and 180ft casing pipes.",
        },
        headers=ngo_headers,
    )
    assert fin_upload.status_code == 201

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 9-12: Run Verification, Show Results, Risk Signals, & Audit Triggers
    # ─────────────────────────────────────────────────────────────────────────
    verify_res = await client.post(f"/api/v1/projects/{proj_id}/verify", headers=ngo_headers)
    assert verify_res.status_code == 200
    ver_data = verify_res.json()["data"]
    assert "overall_score" in ver_data
    assert "overall_quality" in ver_data
    assert "individual_checks" in ver_data

    # Step 10: Inspect Verification Scorecard
    ver_report = await client.get(f"/api/v1/projects/{proj_id}/verification", headers=ngo_headers)
    assert ver_report.status_code == 200
    ver_card = ver_report.json()["data"]
    assert len(ver_card["individual_checks"]) >= 8

    # Step 11: Inspect Risk Assessment
    risk_res = await client.get(f"/api/v1/projects/{proj_id}/risk", headers=ngo_headers)
    assert risk_res.status_code == 200
    risk_data = risk_res.json()["data"]
    assert "risk_score" in risk_data
    assert "risk_level" in risk_data

    # Step 12: Check Audit Recommendation Trigger
    assert "audit_trigger" in risk_data

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 13: Login as Auditor (Inspector Suresh Sharma)
    # ─────────────────────────────────────────────────────────────────────────
    auditor_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "auditor@sih.gov.in", "password": "AuditorPassword123!"},
    )
    assert auditor_login.status_code == 200
    auditor_token = auditor_login.json()["data"]["access_token"]
    auditor_headers = {"Authorization": f"Bearer {auditor_token}"}

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 14: Open Audit Dossier
    # ─────────────────────────────────────────────────────────────────────────
    # Queue / open the audit case
    audit_init = await client.post(
        "/api/v1/audits",
        json={"project_id": proj_id, "scope": "Field verification for live SIH demo Community Water Well"},
        headers=auditor_headers,
    )
    assert audit_init.status_code in (200, 201)
    audit_id = audit_init.json()["data"]["id"]

    dossier_res = await client.get(f"/api/v1/audits/{audit_id}", headers=auditor_headers)
    assert dossier_res.status_code == 200
    dossier = dossier_res.json()["data"]
    assert len(dossier["evidence_timeline"]) >= 3
    assert len(dossier["financial_evidence"]) >= 1

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 15: Confirm Project Audit
    # ─────────────────────────────────────────────────────────────────────────
    decision_res = await client.post(
        f"/api/v1/audits/{audit_id}/decision",
        json={
            "decision": "CONFIRMED",
            "findings": "Physical site inspection confirmed operational solar borewell supplying clean water to rural households. All receipts validated.",
            "notes": "Confirmed 100% genuine project delivery.",
        },
        headers=auditor_headers,
    )
    assert decision_res.status_code == 201

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 16: Recalculate Evidence Score
    # ─────────────────────────────────────────────────────────────────────────
    score_res = await client.get(f"/api/v1/projects/{proj_id}/score", headers=auditor_headers)
    assert score_res.status_code == 200
    score_data = score_res.json()["data"]
    assert score_data["final_score"] >= 80.0
    assert score_data["status"] in ("STRONG_EVIDENCE", "GOOD_EVIDENCE")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 17: Recalculate NGO Transparency Score
    # ─────────────────────────────────────────────────────────────────────────
    ngo_score_res = await client.get(f"/api/v1/ngos/{proj['ngo_id']}/score")
    assert ngo_score_res.status_code == 200
    ngo_score = ngo_score_res.json()["data"]
    assert ngo_score["final_score"] >= 70.0

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 18: Access as Donor (Ananya Patel)
    # ─────────────────────────────────────────────────────────────────────────
    donor_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "donor@philanthropy.org", "password": "DonorPassword123!"},
    )
    assert donor_login.status_code == 200
    donor_token = donor_login.json()["data"]["access_token"]
    donor_headers = {"Authorization": f"Bearer {donor_token}"}

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 19: Search NGO
    # ─────────────────────────────────────────────────────────────────────────
    search_res = await client.get("/api/v1/public/ngos?search=Helping", headers=donor_headers)
    assert search_res.status_code == 200
    ngos = search_res.json()["data"]
    assert len(ngos) >= 1
    found_ngo = next(n for n in ngos if "Helping Villages" in n["name"])

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 20-21: Open NGO Profile & Show Transparency Score + Historical Trend
    # ─────────────────────────────────────────────────────────────────────────
    ngo_profile = await client.get(f"/api/v1/public/ngos/{found_ngo['id']}", headers=donor_headers)
    assert ngo_profile.status_code == 200
    assert ngo_profile.json()["data"]["transparency_score"] >= 70.0

    history_res = await client.get(f"/api/v1/public/ngos/{found_ngo['id']}/score/history", headers=donor_headers)
    assert history_res.status_code == 200
    assert len(history_res.json()["data"]) >= 1

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 22: Open Project Detail
    # ─────────────────────────────────────────────────────────────────────────
    proj_public = await client.get(f"/api/v1/public/projects/{proj_id}", headers=donor_headers)
    assert proj_public.status_code == 200
    pub_data = proj_public.json()["data"]
    assert pub_data["title"] == "Community Water Well - Live Demo"
    assert pub_data["status"] == ProjectStatus.VERIFIED.value

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 23: Show Evidence Timeline & Score Explanation
    # ─────────────────────────────────────────────────────────────────────────
    timeline_res = await client.get(f"/api/v1/public/projects/{proj_id}/timeline", headers=donor_headers)
    assert timeline_res.status_code == 200
    timeline_items = timeline_res.json()["data"]["timeline"]
    assert len(timeline_items) == 3

    score_expl_res = await client.get(f"/api/v1/public/projects/{proj_id}/score", headers=donor_headers)
    assert score_expl_res.status_code == 200
    score_expl = score_expl_res.json()["data"]
    assert "factors" in score_expl
    assert "explanation" in score_expl
