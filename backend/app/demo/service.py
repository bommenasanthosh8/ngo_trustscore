"""
SIH Demonstration Seeding Service.

Generates the complete fictional SIH dataset:
- Fictional NGOs: Helping Villages Foundation & Rural Community Initiative
- Fictional Users: Ramesh Verma (NGO 1), Priya Nair (NGO 2), Suresh Sharma (Auditor),
                   Ananya Patel (Donor), Platform Administrator
- 6 Fictional Demonstration Projects:
  1. Community Water Well (Scenario A: Strong, Verified, 88/100, Low Risk)
  2. School Book Distribution (Scenario B: Medium, Partially Verified, 72/100, Medium Risk)
  3. Medical Camp (Scenario C: Suspicious, Disputed, 41/100, High Risk, Location Mismatch & Fraud)
  4. Community Food Distribution (Scenario D: Pending, Evidence Incomplete)
  5. School Toilet Construction (High-Value Sanitation Audit Queue)
  6. Tree Plantation (Verified Environment Project)
- Real Binary Evidence Image Files & Invoices
- Verification Results & Quality Scorecards
- Multi-factor Risk Assessments
- Immutable Audit Records & Decisions
- Project Disputes
- Historical Score Snapshots & Trend Data
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User, UserRole
from app.core.security import hash_password
from app.demo.media_generator import generate_demo_image_bytes, generate_demo_pdf_bytes, persist_demo_file
from app.models.activity import ActivityLog
from app.models.audit import Audit, AuditDecision
from app.models.dispute import Dispute
from app.models.enums import (
    AuditDecisionType,
    AuditSelectionReason,
    AuditStatus,
    DisputeStatus,
    EvidenceType,
    FinancialConsistencyStatus,
    FinancialDocumentType,
    FinancialValidationStatus,
    LocationStatus,
    NGOVerificationStatus,
    OCRStatus,
    ProjectStatus,
    ProjectType,
    RiskLevel,
    VerificationModel,
    VerificationStatus,
)
from app.models.evidence import Evidence
from app.models.financial_evidence import FinancialEvidence
from app.models.ngo import NGO
from app.models.project import Project
from app.models.risk import RiskAssessment
from app.models.score import ScoreSnapshot
from app.models.verification import VerificationResult


def _make_point(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


async def seed_sih_demonstration_data(db: AsyncSession) -> Dict[str, Any]:
    """
    Populate or reset the database with the complete SIH demonstration dataset.
    Returns a summary report of all generated entities, accounts, and projects.
    """
    now = datetime.now(timezone.utc)

    # ─────────────────────────────────────────────────────────────────────────────
    # 1. PERSONAS & ACCOUNTS
    # ─────────────────────────────────────────────────────────────────────────────
    # Fictional NGO 1: Helping Villages Foundation
    ngo1_query = select(NGO).where(NGO.registration_number == "NGO-IND-2026-HVF01")
    ngo1 = (await db.execute(ngo1_query)).scalar_one_or_none()
    if not ngo1:
        ngo1 = NGO(
            name="Helping Villages Foundation",
            registration_number="NGO-IND-2026-HVF01",
            darpan_id="UP/2026/019842",
            contact_email="contact@helpingvillages.org",
            contact_phone="+91 98765 43210",
            address="Plot 42, Gram Vikas Marg, Varanasi, Uttar Pradesh - 221001",
            description="Empowering rural communities through sustainable infrastructure, healthcare, and educational access.",
            verification_status=NGOVerificationStatus.VERIFIED,
            is_verified=True,
            verified_at=now - timedelta(days=90),
        )
        db.add(ngo1)
        await db.flush()

    # Fictional NGO 2: Rural Community Initiative
    ngo2_query = select(NGO).where(NGO.registration_number == "NGO-IND-2026-RCI02")
    ngo2 = (await db.execute(ngo2_query)).scalar_one_or_none()
    if not ngo2:
        ngo2 = NGO(
            name="Rural Community Initiative",
            registration_number="NGO-IND-2026-RCI02",
            darpan_id="MH/2026/028471",
            contact_email="contact@ruralcommunity.org",
            contact_phone="+91 98765 12345",
            address="78 Gram Swaraj Bhavan, Gadchiroli, Maharashtra - 442605",
            description="Fostering grassroots community self-reliance through nutrition, sanitation, and sustainable afforestation.",
            verification_status=NGOVerificationStatus.VERIFIED,
            is_verified=True,
            verified_at=now - timedelta(days=90),
        )
        db.add(ngo2)
        await db.flush()

    # Seed Users
    users_spec = [
        {
            "email": "lead@helpingvillages.org",
            "password": "NgoPassword123!",
            "full_name": "Ramesh Verma",
            "role": UserRole.NGO,
            "ngo_id": ngo1.id,
        },
        {
            "email": "lead@ruralcommunity.org",
            "password": "NgoPassword123!",
            "full_name": "Priya Nair",
            "role": UserRole.NGO,
            "ngo_id": ngo2.id,
        },
        {
            "email": "auditor@sih.gov.in",
            "password": "AuditorPassword123!",
            "full_name": "Inspector Suresh Sharma",
            "role": UserRole.AUDITOR,
            "ngo_id": None,
        },
        {
            "email": "donor@philanthropy.org",
            "password": "DonorPassword123!",
            "full_name": "Ananya Patel",
            "role": UserRole.DONOR,
            "ngo_id": None,
        },
        {
            "email": "admin@transparency.gov.in",
            "password": "AdminPassword123!",
            "full_name": "Platform Administrator",
            "role": UserRole.ADMIN,
            "ngo_id": None,
        },
    ]

    seeded_users: Dict[str, User] = {}
    for spec in users_spec:
        u_res = await db.execute(select(User).where(User.email == spec["email"]))
        user = u_res.scalar_one_or_none()
        if not user:
            user = User(
                email=spec["email"],
                hashed_password=hash_password(spec["password"]),
                full_name=spec["full_name"],
                role=spec["role"],
                ngo_id=spec["ngo_id"],
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            await db.flush()
        seeded_users[spec["email"]] = user

    user_ngo1 = seeded_users["lead@helpingvillages.org"]
    user_ngo2 = seeded_users["lead@ruralcommunity.org"]
    user_auditor = seeded_users["auditor@sih.gov.in"]

    # ─────────────────────────────────────────────────────────────────────────────
    # 2. SEED THE 6 PROJECTS
    # ─────────────────────────────────────────────────────────────────────────────

    # Clean up any lingering non-demo projects that happen to use demo codes from other tests
    demo_codes = [
        "NGO-WELL-2026-0001",
        "NGO-EDU-2026-0001",
        "NGO-HLTH-2026-0001",
        "NGO-FOOD-2026-0001",
        "NGO-SNTN-2026-0001",
        "NGO-ENVR-2026-0001",
    ]
    for code in demo_codes:
        existing = (await db.execute(select(Project).where(Project.project_code == code))).scalar_one_or_none()
        if existing and (existing.ngo_id not in (ngo1.id, ngo2.id) or existing.status == ProjectStatus.CREATED):
            await db.delete(existing)
            await db.flush()

    # ── Project 1: Community Water Well (Scenario A: Strong, Verified) ─────────
    p1_code = "NGO-WELL-2026-0001"
    p1 = (await db.execute(select(Project).where(Project.project_code == p1_code))).scalar_one_or_none()
    if not p1:
        p1 = Project(
            ngo_id=ngo1.id,
            created_by_id=user_ngo1.id,
            project_code=p1_code,
            title="Community Water Well",
            description="Drilling two deep solar-powered borewells with multi-stage filtration to supply 20,000 L/day potable water to 350 rural families in Rampur village.",
            project_type=ProjectType.WATER_AND_SANITATION,
            verification_model=VerificationModel.PERMANENT,
            status=ProjectStatus.VERIFIED,
            target_amount=200000.0,
            total_budget=200000.0,
            currency="INR",
            expected_beneficiaries=1200,
            expected_outcome="Eliminate waterborne illness and daily 3km water fetching burden for 350 rural households.",
            location_name="Rampur Village Site, Varanasi District, Uttar Pradesh",
            latitude=25.3176,
            longitude=82.9739,
            geofence_radius=500.0,
            gps_accuracy=3.2,
            project_location=_make_point(25.3176, 82.9739),
            start_date=now - timedelta(days=90),
            end_date=now - timedelta(days=10),
            evidence_score=88.0,
            evidence_score_updated_at=now - timedelta(days=5),
            is_publicly_visible=True,
            is_sensitive=False,
        )
        db.add(p1)
        await db.flush()

        # Evidence: BEFORE
        ev1_content, ev1_hash = generate_demo_image_bytes("water_well_before")
        key_ev1 = f"evidence/{p1.id}/water_well_before.jpg"
        persist_demo_file(key_ev1, ev1_content)
        ev1 = Evidence(
            project_id=p1.id,
            submitted_by_id=user_ngo1.id,
            evidence_type=EvidenceType.BEFORE,
            title="Pre-Construction Site Survey & Ground Markings",
            description="Verified parched arid ground prior to drilling operations. Boundary flags established within geofence.",
            storage_key=key_ev1,
            original_filename="site_pre_construction.jpg",
            mime_type="image/jpeg",
            file_size=len(ev1_content),
            file_hash_sha256=ev1_hash,
            captured_at=now - timedelta(days=88),
            uploaded_at=now - timedelta(days=87),
            latitude=25.3176,
            longitude=82.9739,
            gps_accuracy=2.8,
            location_status=LocationStatus.CAPTURED,
            verification_status=VerificationStatus.VERIFIED,
            metadata_summary={"camera": "SM-A525F", "surveyor": "Ramesh Verma"},
        )
        db.add(ev1)

        # Evidence: PROGRESS
        ev2_content, ev2_hash = generate_demo_image_bytes("water_well_progress")
        key_ev2 = f"evidence/{p1.id}/water_well_drilling_progress.jpg"
        persist_demo_file(key_ev2, ev2_content)
        ev2 = Evidence(
            project_id=p1.id,
            submitted_by_id=user_ngo1.id,
            evidence_type=EvidenceType.PROGRESS,
            title="Deep Borewell Rig Drilling & Casing Insertion",
            description="Drilling rig reached 180 feet groundwater aquifer with heavy-duty PVC casing pipe installed.",
            storage_key=key_ev2,
            original_filename="drilling_rig_depth.jpg",
            mime_type="image/jpeg",
            file_size=len(ev2_content),
            file_hash_sha256=ev2_hash,
            captured_at=now - timedelta(days=45),
            uploaded_at=now - timedelta(days=44),
            latitude=25.3177,
            longitude=82.9738,
            gps_accuracy=3.1,
            location_status=LocationStatus.CAPTURED,
            verification_status=VerificationStatus.VERIFIED,
            metadata_summary={"camera": "SM-A525F", "drilling_depth_feet": 180},
        )
        db.add(ev2)

        # Evidence: COMPLETION
        ev3_content, ev3_hash = generate_demo_image_bytes("water_well_completion")
        key_ev3 = f"evidence/{p1.id}/water_well_completion.jpg"
        persist_demo_file(key_ev3, ev3_content)
        ev3 = Evidence(
            project_id=p1.id,
            submitted_by_id=user_ngo1.id,
            evidence_type=EvidenceType.COMPLETION,
            title="Operational Solar Pump & Community Water Collection",
            description="Concrete apron completed with dual overhead 5000L tanks and operational solar pumping station.",
            storage_key=key_ev3,
            original_filename="operational_water_center.jpg",
            mime_type="image/jpeg",
            file_size=len(ev3_content),
            file_hash_sha256=ev3_hash,
            captured_at=now - timedelta(days=12),
            uploaded_at=now - timedelta(days=11),
            latitude=25.3176,
            longitude=82.9739,
            gps_accuracy=2.5,
            location_status=LocationStatus.CAPTURED,
            verification_status=VerificationStatus.VERIFIED,
            metadata_summary={"camera": "SM-A525F", "flow_rate_lpm": 85},
        )
        db.add(ev3)

        # Financial Evidence: ₹2,00,000 Invoice
        fin_bytes, fin_hash = generate_demo_pdf_bytes(
            invoice_number="INV-KASHI-2026-8891",
            vendor_name="Kashi Borewell & Solar Equipment Ltd",
            claimed_amount=200000.0,
            project_title="Community Water Well",
        )
        key_fin1 = f"financial/{p1.id}/invoice_borewell_full.pdf"
        persist_demo_file(key_fin1, fin_bytes)
        fin1 = FinancialEvidence(
            project_id=p1.id,
            submitted_by_id=user_ngo1.id,
            document_type=FinancialDocumentType.INVOICE,
            claimed_amount=200000.0,
            extracted_amount=200000.0,
            currency="INR",
            document_date=now - timedelta(days=15),
            vendor_name="Kashi Borewell & Solar Equipment Ltd",
            invoice_number="INV-KASHI-2026-8891",
            description="Solar pump, drilling rig hire, 180ft casing pipes, concrete apron material.",
            storage_key=key_fin1,
            original_filename="kashi_borewell_invoice.pdf",
            mime_type="application/pdf",
            file_size=len(fin_bytes),
            document_hash=fin_hash,
            ocr_status=OCRStatus.COMPLETED,
            ocr_engine="pytesseract_demo_engine",
            validation_status=FinancialValidationStatus.VALID,
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add(fin1)

        # Risk Assessment: LOW
        risk1 = RiskAssessment(
            project_id=p1.id,
            risk_level=RiskLevel.LOW,
            risk_score=14.0,
            factors={
                "location_mismatch": 0.0,
                "financial_discrepancy": 0.0,
                "duplicate_media": 0.0,
                "suspicious_metadata": 0.0,
                "missing_timeline": 0.0,
                "failed_submissions": 0.0,
                "high_project_value": 14.0,
                "previous_disputes": 0.0,
                "unusual_patterns": 0.0,
                "incomplete_evidence": 0.0,
            },
            assessed_at=now - timedelta(days=10),
        )
        db.add(risk1)

        # Audit & Concluded Decision: CONFIRMED
        audit1 = Audit(
            project_id=p1.id,
            auditor_id=user_auditor.id,
            selection_reason=AuditSelectionReason.HIGH_VALUE,
            status=AuditStatus.CONCLUDED,
            scope="Comprehensive physical inspection of solar borewell site, pump flow testing, and equipment invoice audit.",
            findings="Independent physical inspection confirmed 100% operational facility. Flow meter confirms 85 L/min potable output. Vendor invoices verified authentic.",
            created_at=now - timedelta(days=8),
        )
        db.add(audit1)
        await db.flush()

        dec1 = AuditDecision(
            audit_id=audit1.id,
            decision=AuditDecisionType.CONFIRMED,
            findings="Borewell site inspected in person. High quality construction verified and geofenced site confirms coordinates. Water is clean and serving the village.",
            notes="Confirmed 100% project delivery.",
            supporting_evidence={"inspection_date": (now - timedelta(days=6)).isoformat(), "inspector": "Inspector Suresh Sharma"},
            is_superseded=False,
            decided_by_id=user_auditor.id,
            decided_at=now - timedelta(days=5),
        )
        db.add(dec1)

        # Historical Score Snapshots
        for offset, score_val in [(60, 68.0), (30, 76.0), (15, 82.0), (5, 88.0)]:
            snap = ScoreSnapshot(
                project_id=p1.id,
                composite_score=score_val,
                breakdown={"location": 18.0, "timeline": 18.0, "media": 18.0, "financial": 18.0, "identity": 8.0, "audit": 8.0},
                calculated_at=now - timedelta(days=offset),
            )
            db.add(snap)


    # ── Project 2: School Book Distribution (Scenario B: Medium, Partially Verified)
    p2_code = "NGO-EDU-2026-0001"
    p2 = (await db.execute(select(Project).where(Project.project_code == p2_code))).scalar_one_or_none()
    if not p2:
        p2 = Project(
            ngo_id=ngo1.id,
            created_by_id=user_ngo1.id,
            project_code=p2_code,
            title="School Book Distribution",
            description="Distribution of 250 comprehensive academic textbooks, STEM notebooks, and geometry sets to tribal students at Bhamragad Ashram School.",
            project_type=ProjectType.EDUCATION,
            verification_model=VerificationModel.ONE_TIME_EVENT,
            status=ProjectStatus.PARTIALLY_VERIFIED,
            target_amount=75000.0,
            total_budget=75000.0,
            currency="INR",
            expected_beneficiaries=250,
            expected_outcome="Provide 100% textbook coverage for Grades 1–8 tribal residential students.",
            location_name="Zilla Parishad Tribal Ashram School, Bhamragad, Maharashtra",
            latitude=19.3850,
            longitude=80.3540,
            geofence_radius=750.0,
            gps_accuracy=4.1,
            project_location=_make_point(19.3850, 80.3540),
            start_date=now - timedelta(days=35),
            end_date=now + timedelta(days=10),
            evidence_score=72.0,
            evidence_score_updated_at=now - timedelta(days=3),
            is_publicly_visible=True,
            is_sensitive=False,
        )
        db.add(p2)
        await db.flush()

        # Evidence: BEFORE & PROGRESS (Missing COMPLETION)
        ev_b1, hash_b1 = generate_demo_image_bytes("books_stock_warehouse")
        key_b1 = f"evidence/{p2.id}/books_procurement.jpg"
        persist_demo_file(key_b1, ev_b1)
        db.add(Evidence(
            project_id=p2.id,
            submitted_by_id=user_ngo1.id,
            evidence_type=EvidenceType.BEFORE,
            title="Warehouse Receipt of Textbooks Package",
            description="Received 180 textbook packages from district supplier awaiting school transport.",
            storage_key=key_b1,
            original_filename="textbooks_consignment.jpg",
            mime_type="image/jpeg",
            file_size=len(ev_b1),
            file_hash_sha256=hash_b1,
            captured_at=now - timedelta(days=30),
            uploaded_at=now - timedelta(days=29),
            latitude=19.3850,
            longitude=80.3540,
            gps_accuracy=4.0,
            location_status=LocationStatus.CAPTURED,
            verification_status=VerificationStatus.VERIFIED,
        ))

        ev_b2, hash_b2 = generate_demo_image_bytes("books_handover_phase1")
        key_b2 = f"evidence/{p2.id}/books_distribution_handover.jpg"
        persist_demo_file(key_b2, ev_b2)
        db.add(Evidence(
            project_id=p2.id,
            submitted_by_id=user_ngo1.id,
            evidence_type=EvidenceType.PROGRESS,
            title="Classroom Handover Phase 1 (Grades 1-4)",
            description="Handed over 180 textbook sets to primary students with principal acknowledgement.",
            storage_key=key_b2,
            original_filename="primary_class_handover.jpg",
            mime_type="image/jpeg",
            file_size=len(ev_b2),
            file_hash_sha256=hash_b2,
            captured_at=now - timedelta(days=14),
            uploaded_at=now - timedelta(days=13),
            latitude=19.3851,
            longitude=80.3541,
            gps_accuracy=3.8,
            location_status=LocationStatus.CAPTURED,
            verification_status=VerificationStatus.VERIFIED,
        ))

        # Financial Evidence: ₹55,000 supported vs ₹75,000 claimed
        fin_b_bytes, fin_b_hash = generate_demo_pdf_bytes(
            invoice_number="INV-VIDYA-2026-4412",
            vendor_name="Vidya Book Depot & Educational Supplies",
            claimed_amount=55000.0,
            project_title="School Book Distribution",
        )
        key_fin_b = f"financial/{p2.id}/invoice_vidya_books.pdf"
        persist_demo_file(key_fin_b, fin_b_bytes)
        db.add(FinancialEvidence(
            project_id=p2.id,
            submitted_by_id=user_ngo1.id,
            document_type=FinancialDocumentType.INVOICE,
            claimed_amount=75000.0,
            extracted_amount=55000.0,
            currency="INR",
            document_date=now - timedelta(days=28),
            vendor_name="Vidya Book Depot & Educational Supplies",
            invoice_number="INV-VIDYA-2026-4412",
            description="Batch 1 primary school textbooks and geometry sets.",
            storage_key=key_fin_b,
            original_filename="vidya_books_receipt.pdf",
            mime_type="application/pdf",
            file_size=len(fin_b_bytes),
            document_hash=fin_b_hash,
            ocr_status=OCRStatus.COMPLETED,
            validation_status=FinancialValidationStatus.AMOUNT_MISMATCH,
            validation_flags=["OCR_AMOUNT_MISMATCH"],
            verification_status=VerificationStatus.FLAGGED,
        ))

        # Risk Assessment: MEDIUM (Score 42)
        db.add(RiskAssessment(
            project_id=p2.id,
            risk_level=RiskLevel.MEDIUM,
            risk_score=42.0,
            factors={"missing_timeline": 18.0, "financial_discrepancy": 15.0, "incomplete_evidence": 9.0},
            assessed_at=now - timedelta(days=10),
        ))

        # Audit: PARTIALLY_CONFIRMED
        audit2 = Audit(
            project_id=p2.id,
            auditor_id=user_auditor.id,
            selection_reason=AuditSelectionReason.RANDOM_SAMPLE,
            status=AuditStatus.CONCLUDED,
            scope="Review book distribution receipts and student delivery logs.",
            findings="Confirmed distribution of 180 textbook sets (₹55,000 value). Remaining 70 sets delayed due to washed out bridge.",
            created_at=now - timedelta(days=7),
        )
        db.add(audit2)
        await db.flush()

        db.add(AuditDecision(
            audit_id=audit2.id,
            decision=AuditDecisionType.PARTIALLY_CONFIRMED,
            findings="Confirmed partial distribution of 180 packages. Supported expenditure validates ₹55,000 of ₹75,000 allocation.",
            notes="Second batch to be verified post-monsoon.",
            is_superseded=False,
            decided_by_id=user_auditor.id,
            decided_at=now - timedelta(days=3),
        ))

        for offset, score_val in [(30, 58.0), (15, 65.0), (3, 72.0)]:
            db.add(ScoreSnapshot(
                project_id=p2.id,
                composite_score=score_val,
                breakdown={"location": 16.0, "timeline": 14.0, "media": 14.0, "financial": 12.0, "identity": 8.0, "audit": 8.0},
                calculated_at=now - timedelta(days=offset),
            ))


    # ── Project 3: Medical Camp (Scenario C: Suspicious, Disputed) ────────────
    p3_code = "NGO-HLTH-2026-0001"
    p3 = (await db.execute(select(Project).where(Project.project_code == p3_code))).scalar_one_or_none()
    if not p3:
        p3 = Project(
            ngo_id=ngo1.id,
            created_by_id=user_ngo1.id,
            project_code=p3_code,
            title="Medical Camp",
            description="3-day multi-specialty rural health camp offering free diagnostic health screenings and generic medication.",
            project_type=ProjectType.HEALTHCARE,
            verification_model=VerificationModel.ONE_TIME_EVENT,
            status=ProjectStatus.DISPUTED,
            target_amount=120000.0,
            total_budget=120000.0,
            currency="INR",
            expected_beneficiaries=800,
            expected_outcome="Screen 800 villagers for hypertension, diabetes, and provide free pediatric vitamins.",
            location_name="Trimbakeshwar Rural Community Hall, Nashik, Maharashtra",
            latitude=19.9324,
            longitude=73.5308,
            geofence_radius=400.0,
            gps_accuracy=3.5,
            project_location=_make_point(19.9324, 73.5308),
            start_date=now - timedelta(days=20),
            end_date=now - timedelta(days=17),
            evidence_score=41.0,
            evidence_score_updated_at=now - timedelta(days=2),
            is_publicly_visible=True,
            is_sensitive=True,
        )
        db.add(p3)
        await db.flush()

        # Evidence with LOCATION MISMATCH (14.2 km away) & Duplicate Hash
        ev_c1, hash_c1 = generate_demo_image_bytes("reused_medical_photo_tag")
        key_c1 = f"evidence/{p3.id}/reused_clinic_photo.jpg"
        persist_demo_file(key_c1, ev_c1)
        db.add(Evidence(
            project_id=p3.id,
            submitted_by_id=user_ngo1.id,
            evidence_type=EvidenceType.PROGRESS,
            title="Patient Registration & Screening Queue",
            description="Crowd registration table for medical diagnostics.",
            storage_key=key_c1,
            original_filename="screening_queue_day1.jpg",
            mime_type="image/jpeg",
            file_size=len(ev_c1),
            file_hash_sha256=hash_c1,
            captured_at=now - timedelta(days=19),
            uploaded_at=now - timedelta(days=18),
            latitude=19.8050,  # 14.2 km distance from 19.9324
            longitude=73.6510, # Location mismatch!
            gps_accuracy=5.0,
            location_status=LocationStatus.CAPTURED,
            verification_status=VerificationStatus.REJECTED,
            metadata_summary={"beneficiary_name": "Sita Devi", "phone": "9811223344", "syndrome": "Fever"},
        ))

        # Financial Discrepancy: Claimed ₹1,20,000 but invoice is only ₹40,000
        fin_c_bytes, fin_c_hash = generate_demo_pdf_bytes(
            invoice_number="INV-NASHIK-MED-101",
            vendor_name="Nashik Generic Pharma Distributors",
            claimed_amount=40000.0,
            project_title="Medical Camp",
        )
        key_fin_c = f"financial/{p3.id}/invoice_partial_pharma.pdf"
        persist_demo_file(key_fin_c, fin_c_bytes)
        db.add(FinancialEvidence(
            project_id=p3.id,
            submitted_by_id=user_ngo1.id,
            document_type=FinancialDocumentType.INVOICE,
            claimed_amount=120000.0,
            extracted_amount=40000.0,
            currency="INR",
            document_date=now - timedelta(days=19),
            vendor_name="Nashik Generic Pharma Distributors",
            invoice_number="INV-NASHIK-MED-101",
            description="Generic vitamins and antibiotics batch.",
            storage_key=key_fin_c,
            original_filename="pharma_invoice.pdf",
            mime_type="application/pdf",
            file_size=len(fin_c_bytes),
            document_hash=fin_c_hash,
            ocr_status=OCRStatus.COMPLETED,
            validation_status=FinancialValidationStatus.AMOUNT_MISMATCH,
            validation_flags=["OCR_AMOUNT_MISMATCH", "INSUFFICIENT_SUPPORTED_EXPENDITURE"],
            verification_status=VerificationStatus.FLAGGED,
        ))

        # Risk Assessment: HIGH (Score 85)
        db.add(RiskAssessment(
            project_id=p3.id,
            risk_level=RiskLevel.HIGH,
            risk_score=85.0,
            factors={
                "location_mismatch": 35.0,
                "financial_discrepancy": 30.0,
                "duplicate_media": 20.0,
            },
            assessed_at=now - timedelta(days=17),
        ))

        # Audit with DISCREPANCY Decision
        audit3 = Audit(
            project_id=p3.id,
            auditor_id=user_auditor.id,
            selection_reason=AuditSelectionReason.HIGH_RISK,
            status=AuditStatus.CONCLUDED,
            scope="Forensic examination of geotag coordinates, duplicate photo hash, and pharma invoices.",
            findings="Evidence photograph was taken 14.2km outside designated clinic geofence. Validated receipts only account for ₹40,000 of ₹1,20,000 claimed expenditure.",
            created_at=now - timedelta(days=15),
        )
        db.add(audit3)
        await db.flush()

        db.add(AuditDecision(
            audit_id=audit3.id,
            decision=AuditDecisionType.DISCREPANCY,
            findings="Location mismatch detected: Geotag is 14.2km from registered hall. Receipts substantiate only 33% of claimed budget. Integrity flags confirmed.",
            notes="Flagged as discrepancy. Awaiting NGO response.",
            is_superseded=False,
            decided_by_id=user_auditor.id,
            decided_at=now - timedelta(days=10),
        ))

        # Active Dispute lodged by NGO
        db.add(Dispute(
            project_id=p3.id,
            raised_by_id=user_ngo1.id,
            reason="Heavy waterlogging at primary community hall forced immediate relocation to high ground school 14km away. Secondary invoice for diagnostic doctor fees (₹80,000) was omitted due to field internet breakdown. Requesting administrative review.",
            status=DisputeStatus.OPEN,
        ))

        db.add(ScoreSnapshot(
            project_id=p3.id,
            composite_score=41.0,
            breakdown={"location": 4.0, "timeline": 8.0, "media": 5.0, "financial": 6.0, "identity": 8.0, "audit": 10.0},
            calculated_at=now - timedelta(days=2),
        ))


    # ── Project 4: Community Food Distribution (Scenario D: Pending) ──────────
    p4_code = "NGO-FOOD-2026-0001"
    p4 = (await db.execute(select(Project).where(Project.project_code == p4_code))).scalar_one_or_none()
    if not p4:
        p4 = Project(
            ngo_id=ngo2.id,
            created_by_id=user_ngo2.id,
            project_code=p4_code,
            title="Community Food Distribution",
            description="Procurement and distribution of 400 dry grocery and pulse rations kits to vulnerable families in cyclone-impacted Sundarbans.",
            project_type=ProjectType.FOOD_DISTRIBUTION,
            verification_model=VerificationModel.ONE_TIME_EVENT,
            status=ProjectStatus.EVIDENCE_COLLECTION,  # Pending completion
            target_amount=50000.0,
            total_budget=50000.0,
            currency="INR",
            expected_beneficiaries=400,
            expected_outcome="Deliver 15-day staple food security packages to 400 isolated island families.",
            location_name="Gosaba Island Distribution Point, Sundarbans, West Bengal",
            latitude=22.1648,
            longitude=88.8094,
            geofence_radius=1000.0,
            gps_accuracy=4.2,
            project_location=_make_point(22.1648, 88.8094),
            start_date=now - timedelta(days=6),
            end_date=now + timedelta(days=20),
            evidence_score=35.0,
            evidence_score_updated_at=now - timedelta(days=1),
            is_publicly_visible=True,
            is_sensitive=False,
        )
        db.add(p4)
        await db.flush()

        # Only 1 initial BEFORE photo (Incomplete evidence)
        ev_d1, hash_d1 = generate_demo_image_bytes("food_rations_procurement")
        key_d1 = f"evidence/{p4.id}/procured_ration_sacks.jpg"
        persist_demo_file(key_d1, ev_d1)
        db.add(Evidence(
            project_id=p4.id,
            submitted_by_id=user_ngo2.id,
            evidence_type=EvidenceType.BEFORE,
            title="Procurement of Rice and Lentil Sacks",
            description="Loaded initial ration sacks on boat for island transit.",
            storage_key=key_d1,
            original_filename="ration_sacks_boat.jpg",
            mime_type="image/jpeg",
            file_size=len(ev_d1),
            file_hash_sha256=hash_d1,
            captured_at=now - timedelta(days=4),
            uploaded_at=now - timedelta(days=3),
            latitude=22.1648,
            longitude=88.8094,
            gps_accuracy=3.5,
            location_status=LocationStatus.CAPTURED,
            verification_status=VerificationStatus.PENDING,
        ))

        db.add(RiskAssessment(
            project_id=p4.id,
            risk_level=RiskLevel.MEDIUM,
            risk_score=48.0,
            factors={"incomplete_evidence": 25.0, "missing_timeline": 15.0, "financial_discrepancy": 8.0},
            assessed_at=now - timedelta(days=1),
        ))

        db.add(ScoreSnapshot(
            project_id=p4.id,
            composite_score=35.0,
            breakdown={"location": 12.0, "timeline": 5.0, "media": 8.0, "financial": 0.0, "identity": 8.0, "audit": 2.0},
            calculated_at=now - timedelta(days=1),
        ))


    # ── Project 5: School Toilet Construction (High-Value Sanitation Audit Queue)
    p5_code = "NGO-SNTN-2026-0001"
    p5 = (await db.execute(select(Project).where(Project.project_code == p5_code))).scalar_one_or_none()
    if not p5:
        p5 = Project(
            ngo_id=ngo2.id,
            created_by_id=user_ngo2.id,
            project_code=p5_code,
            title="School Toilet Construction",
            description="Construction of dedicated twin toilet blocks with running water and sanitary disposal for tribal girl students.",
            project_type=ProjectType.SANITATION,
            verification_model=VerificationModel.PERMANENT,
            status=ProjectStatus.UNDER_VERIFICATION,
            target_amount=300000.0,
            total_budget=300000.0,
            currency="INR",
            expected_beneficiaries=350,
            expected_outcome="Reduce girl dropout rates by providing dignified, hygienic school sanitation blocks.",
            location_name="Sonbhadra Tribal Girls High School, Sonbhadra, Uttar Pradesh",
            latitude=24.6850,
            longitude=83.0650,
            geofence_radius=500.0,
            gps_accuracy=3.0,
            project_location=_make_point(24.6850, 83.0650),
            start_date=now - timedelta(days=60),
            end_date=now - timedelta(days=5),
            evidence_score=79.0,
            evidence_score_updated_at=now - timedelta(days=2),
            is_publicly_visible=True,
            is_sensitive=False,
        )
        db.add(p5)
        await db.flush()

        # Audit initiated in queue
        audit5 = Audit(
            project_id=p5.id,
            auditor_id=user_auditor.id,
            selection_reason=AuditSelectionReason.HIGH_VALUE,
            status=AuditStatus.INITIATED,
            scope="Civil engineer verification of structural brickwork, plumbing connections, and septic tank compliance.",
            findings=None,
            created_at=now - timedelta(days=2),
        )
        db.add(audit5)

        db.add(ScoreSnapshot(
            project_id=p5.id,
            composite_score=79.0,
            breakdown={"location": 16.0, "timeline": 16.0, "media": 16.0, "financial": 15.0, "identity": 8.0, "audit": 8.0},
            calculated_at=now - timedelta(days=2),
        ))


    # ── Project 6: Tree Plantation (Verified Environment Project) ──────────────
    p6_code = "NGO-ENVR-2026-0001"
    p6 = (await db.execute(select(Project).where(Project.project_code == p6_code))).scalar_one_or_none()
    if not p6:
        p6 = Project(
            ngo_id=ngo2.id,
            created_by_id=user_ngo2.id,
            project_code=p6_code,
            title="Tree Plantation",
            description="Community-led afforestation of 2,500 indigenous fruit-bearing and shade saplings with bio-fencing in Araku Valley.",
            project_type=ProjectType.ENVIRONMENT,
            verification_model=VerificationModel.PERMANENT,
            status=ProjectStatus.VERIFIED,
            target_amount=40000.0,
            total_budget=40000.0,
            currency="INR",
            expected_beneficiaries=2500,
            expected_outcome="Restore green canopy cover and supply fruit crops to tribal self-help collectives.",
            location_name="Araku Valley Community Forest, Alluri Sitharama Raju District, Andhra Pradesh",
            latitude=18.3273,
            longitude=82.8775,
            geofence_radius=1500.0,
            gps_accuracy=3.8,
            project_location=_make_point(18.3273, 82.8775),
            start_date=now - timedelta(days=50),
            end_date=now - timedelta(days=15),
            evidence_score=91.0,
            evidence_score_updated_at=now - timedelta(days=5),
            is_publicly_visible=True,
            is_sensitive=False,
        )
        db.add(p6)
        await db.flush()

        db.add(ScoreSnapshot(
            project_id=p6.id,
            composite_score=91.0,
            breakdown={"location": 19.0, "timeline": 18.0, "media": 18.0, "financial": 18.0, "identity": 9.0, "audit": 9.0},
            calculated_at=now - timedelta(days=5),
        ))

    # ─────────────────────────────────────────────────────────────────────────────
    # 3. HISTORICAL SCORE SNAPSHOTS FOR NGOS
    # ─────────────────────────────────────────────────────────────────────────────
    # Helping Villages Foundation Historical Trend
    for offset, ngo_score in [(60, 62.0), (30, 71.0), (5, 78.5)]:
        snap_ngo1 = ScoreSnapshot(
            ngo_id=ngo1.id,
            composite_score=ngo_score,
            breakdown={"verified_ratio": 0.65, "average_project_score": ngo_score},
            calculated_at=now - timedelta(days=offset),
        )
        db.add(snap_ngo1)

    # Rural Community Initiative Historical Trend
    for offset, ngo_score in [(60, 60.0), (30, 68.0), (5, 74.0)]:
        snap_ngo2 = ScoreSnapshot(
            ngo_id=ngo2.id,
            composite_score=ngo_score,
            breakdown={"verified_ratio": 0.70, "average_project_score": ngo_score},
            calculated_at=now - timedelta(days=offset),
        )
        db.add(snap_ngo2)

    # Commit all seeded models
    await db.commit()

    return {
        "status": "SUCCESS",
        "message": "Complete fictional SIH demonstration dataset seeded successfully.",
        "ngos": [
            {"id": str(ngo1.id), "name": ngo1.name, "score": 78.5},
            {"id": str(ngo2.id), "name": ngo2.name, "score": 74.0},
        ],
        "personas": [
            {"name": "Ramesh Verma", "role": "NGO (Helping Villages)", "email": "lead@helpingvillages.org", "password": "NgoPassword123!"},
            {"name": "Priya Nair", "role": "NGO (Rural Community)", "email": "lead@ruralcommunity.org", "password": "NgoPassword123!"},
            {"name": "Inspector Suresh Sharma", "role": "AUDITOR", "email": "auditor@sih.gov.in", "password": "AuditorPassword123!"},
            {"name": "Ananya Patel", "role": "DONOR", "email": "donor@philanthropy.org", "password": "DonorPassword123!"},
            {"name": "Platform Administrator", "role": "ADMIN", "email": "admin@transparency.gov.in", "password": "AdminPassword123!"},
        ],
        "projects": [
            {"title": "Community Water Well", "code": p1_code, "scenario": "A (Strong)", "status": "VERIFIED", "score": 88.0, "risk": "LOW"},
            {"title": "School Book Distribution", "code": p2_code, "scenario": "B (Medium)", "status": "PARTIALLY_VERIFIED", "score": 72.0, "risk": "MEDIUM"},
            {"title": "Medical Camp", "code": p3_code, "scenario": "C (Suspicious)", "status": "DISPUTED", "score": 41.0, "risk": "HIGH"},
            {"title": "Community Food Distribution", "code": p4_code, "scenario": "D (Pending)", "status": "PENDING", "score": 35.0, "risk": "MEDIUM"},
            {"title": "School Toilet Construction", "code": p5_code, "scenario": "High-Value Audit Queue", "status": "UNDER_VERIFICATION", "score": 79.0, "risk": "LOW"},
            {"title": "Tree Plantation", "code": p6_code, "scenario": "Verified Environment", "status": "VERIFIED", "score": 91.0, "risk": "LOW"},
        ],
    }
