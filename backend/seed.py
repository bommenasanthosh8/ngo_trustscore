"""
Database seeding script.
Usage:
    python seed.py [--admin-only]
"""
import asyncio
import sys
import uuid

from sqlalchemy import select
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.ngo import NGO
from app.models.user import User

settings = get_settings()


async def seed():
    print(f"Connecting to database: {settings.APP_ENV} environment ({settings.DATABASE_URL.split('@')[-1]})...")
    try:
        async with AsyncSessionLocal() as session:
            # 1. Seed Platform Admin
            admin_email = settings.ADMIN_EMAIL
        admin_res = await session.execute(select(User).where(User.email == admin_email))
        existing_admin = admin_res.scalar_one_or_none()

        if not existing_admin:
            admin = User(
                email=admin_email,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                full_name="Platform Administrator",
                role=UserRole.ADMIN,
                is_verified=True,
                is_active=True,
            )
            session.add(admin)
            print(f"Created default admin: {admin_email}")
        else:
            print(f"Admin already exists: {admin_email}")

        if "--admin-only" not in sys.argv:
            # 2. Seed Demo NGO
            ngo_res = await session.execute(
                select(NGO).where(NGO.registration_number == "NGO-DEMO-001")
            )
            demo_ngo = ngo_res.scalar_one_or_none()
            if not demo_ngo:
                demo_ngo = NGO(
                    name="Global Hope Initiative",
                    registration_number="NGO-DEMO-001",
                    darpan_id="DL/2026/001234",
                    contact_email="contact@globalhope.org",
                    contact_phone="+91 9876543210",
                    website="https://globalhope.org",
                    is_verified=True,
                )
                session.add(demo_ngo)
                await session.flush()
                print("Created demo NGO: Global Hope Initiative")

            # 3. Seed Demo NGO User
            ngo_user_email = "lead@globalhope.org"
            ngo_user_res = await session.execute(
                select(User).where(User.email == ngo_user_email)
            )
            if not ngo_user_res.scalar_one_or_none():
                ngo_user = User(
                    email=ngo_user_email,
                    hashed_password=hash_password("NgoPassword123!"),
                    full_name="Ananya Sen",
                    role=UserRole.NGO,
                    ngo_id=demo_ngo.id,
                    is_verified=True,
                )
                session.add(ngo_user)
                print(f"Created demo NGO user: {ngo_user_email}")

            # 4. Seed Demo Auditor
            auditor_email = "auditor@gov.in"
            auditor_res = await session.execute(
                select(User).where(User.email == auditor_email)
            )
            if not auditor_res.scalar_one_or_none():
                auditor = User(
                    email=auditor_email,
                    hashed_password=hash_password("AuditorPass123!"),
                    full_name="Inspector Rajesh Verma",
                    role=UserRole.AUDITOR,
                    is_verified=True,
                )
                session.add(auditor)
                print(f"Created demo Auditor: {auditor_email}")

            # 5. Seed Demo Donor
            donor_email = "donor@philanthropy.org"
            donor_res = await session.execute(
                select(User).where(User.email == donor_email)
            )
            if not donor_res.scalar_one_or_none():
                donor = User(
                    email=donor_email,
                    hashed_password=hash_password("DonorPass123!"),
                    full_name="Vikram Mehta",
                    role=UserRole.DONOR,
                    is_verified=True,
                )
                session.add(donor)
                print(f"Created demo Donor: {donor_email}")

            # 6. Seed Realistic Fictional Projects
            from datetime import datetime, timezone, timedelta
            from geoalchemy2.elements import WKTElement
            from app.models.enums import ProjectStatus, ProjectType, VerificationModel
            from app.models.project import Project

            now = datetime.now(timezone.utc)
            projects_data = [
                {
                    "project_code": "NGO-WELL-2026-0001",
                    "title": "Rural Clean Water Borewell & Filtration Project",
                    "description": "Drilling two deep solar-powered borewells and installing multi-stage filtration to eliminate waterborne fluorosis in Rampur village.",
                    "project_type": ProjectType.WATER_AND_SANITATION,
                    "verification_model": VerificationModel.PERMANENT,
                    "status": ProjectStatus.EVIDENCE_COLLECTION,
                    "target_amount": 450000.0,
                    "expected_beneficiaries": 1800,
                    "expected_outcome": "Supply 20,000 liters/day potable drinking water to 350 rural families with continuous water quality monitoring.",
                    "location_name": "Rampur Village, Varanasi District, Uttar Pradesh",
                    "latitude": 25.3176,
                    "longitude": 82.9739,
                    "geofence_radius": 500.0,
                    "gps_accuracy": 3.2,
                    "start_date": now - timedelta(days=60),
                    "end_date": now + timedelta(days=120),
                    "evidence_score": 78.5,
                },
                {
                    "project_code": "NGO-EDU-2026-0001",
                    "title": "Tribal High School Solar Electrification & STEM Lab",
                    "description": "Equipping remote tribal residential ashram school with 10kW off-grid solar power and interactive STEM science laboratory.",
                    "project_type": ProjectType.EDUCATION,
                    "verification_model": VerificationModel.PERMANENT,
                    "status": ProjectStatus.FUNDING,
                    "target_amount": 680000.0,
                    "expected_beneficiaries": 420,
                    "expected_outcome": "Uninterrupted 24/7 solar electricity and digital smart classroom curriculum access for 420 tribal students.",
                    "location_name": "Bhamragad Ashram School, Gadchiroli, Maharashtra",
                    "latitude": 19.3850,
                    "longitude": 80.3540,
                    "geofence_radius": 750.0,
                    "gps_accuracy": 4.5,
                    "start_date": now - timedelta(days=15),
                    "end_date": now + timedelta(days=180),
                    "evidence_score": None,
                },
                {
                    "project_code": "NGO-HLTH-2026-0001",
                    "title": "Maternal & Child Health Primary Care Clinic",
                    "description": "Constructing and equipping a rural maternal care extension wing with neonatal resuscitation and diagnostic ultrasound facilities.",
                    "project_type": ProjectType.HEALTHCARE,
                    "verification_model": VerificationModel.PERMANENT,
                    "status": ProjectStatus.VERIFIED,
                    "target_amount": 1200000.0,
                    "expected_beneficiaries": 3500,
                    "expected_outcome": "Eliminate maternal transport delays; provide 100% institutional deliveries for high-risk tribal pregnancies.",
                    "location_name": "Trimbakeshwar Rural Health Center, Nashik, Maharashtra",
                    "latitude": 19.9324,
                    "longitude": 73.5308,
                    "geofence_radius": 400.0,
                    "gps_accuracy": 2.1,
                    "start_date": now - timedelta(days=180),
                    "end_date": now - timedelta(days=20),
                    "evidence_score": 94.0,
                },
                {
                    "project_code": "NGO-RELF-2026-0001",
                    "title": "Monsoon Flood Rapid Relief & Emergency Ration Distribution",
                    "description": "Emergency distribution of essential food kits, water purification units, and hygiene kits to monsoon flood victims.",
                    "project_type": ProjectType.RELIEF_DISTRIBUTION,
                    "verification_model": VerificationModel.ONE_TIME_EVENT,
                    "status": ProjectStatus.UNDER_VERIFICATION,
                    "target_amount": 350000.0,
                    "expected_beneficiaries": 1250,
                    "expected_outcome": "Direct delivery of 1,250 food & medical ration packages within 72 hours of flood displacement.",
                    "location_name": "Chiplun Relief Distribution Ground, Ratnagiri, Maharashtra",
                    "latitude": 17.5323,
                    "longitude": 73.5186,
                    "geofence_radius": 1000.0,
                    "gps_accuracy": 5.0,
                    "start_date": now - timedelta(days=40),
                    "end_date": now + timedelta(days=10),
                    "evidence_score": 86.0,
                },
                {
                    "project_code": "NGO-ENVR-2026-0001",
                    "title": "Coastal Mangrove Bio-Shield & Wetland Restoration",
                    "description": "Community-led afforestation of 50,000 saline-resistant mangrove saplings along cyclone-vulnerable river embankments.",
                    "project_type": ProjectType.ENVIRONMENT,
                    "verification_model": VerificationModel.PERMANENT,
                    "status": ProjectStatus.CREATED,
                    "target_amount": 890000.0,
                    "expected_beneficiaries": 5000,
                    "expected_outcome": "Restore 15 hectares of coastal mangrove buffer, mitigating soil erosion and protecting fishing villages from tidal surges.",
                    "location_name": "Gosaba Wetland Reserve, Sundarbans, West Bengal",
                    "latitude": 22.1648,
                    "longitude": 88.8094,
                    "geofence_radius": 2000.0,
                    "gps_accuracy": None,
                    "start_date": now + timedelta(days=10),
                    "end_date": now + timedelta(days=365),
                    "evidence_score": None,
                },
            ]

            for p_data in projects_data:
                code = p_data["project_code"]
                p_res = await session.execute(select(Project).where(Project.project_code == code))
                if not p_res.scalar_one_or_none():
                    lat = p_data["latitude"]
                    lon = p_data["longitude"]
                    p = Project(
                        ngo_id=demo_ngo.id,
                        created_by_id=ngo_user.id,
                        project_code=code,
                        title=p_data["title"],
                        description=p_data["description"],
                        project_type=p_data["project_type"],
                        verification_model=p_data["verification_model"],
                        status=p_data["status"],
                        target_amount=p_data["target_amount"],
                        total_budget=p_data["target_amount"],
                        currency="INR",
                        expected_beneficiaries=p_data["expected_beneficiaries"],
                        expected_outcome=p_data["expected_outcome"],
                        location_name=p_data["location_name"],
                        latitude=lat,
                        longitude=lon,
                        geofence_radius=p_data["geofence_radius"],
                        gps_accuracy=p_data["gps_accuracy"],
                        project_location=WKTElement(f"POINT({lon} {lat})", srid=4326),
                        start_date=p_data["start_date"],
                        end_date=p_data["end_date"],
                        evidence_score=p_data["evidence_score"],
                        is_publicly_visible=True,
                    )
                    session.add(p)
                    print(f"Created project: [{code}] {p_data['title']}")
                else:
                    print(f"Project already exists: [{code}]")

        await session.commit()
        print("Database seeding completed successfully.")
    except Exception as e:
        print(f"Notice: Database connection or execution could not complete: {e}")
        print("When running against local PostgreSQL, ensure PostgreSQL daemon is active on port 5432.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
