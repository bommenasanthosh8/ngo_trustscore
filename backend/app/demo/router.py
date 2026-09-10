"""
Demo API Router — Endpoints for automated SIH demonstration seeding and persona lookup.
"""
from __future__ import annotations

from fastapi import APIRouter, status

from app.core.responses import ok
from app.demo.service import seed_sih_demonstration_data
from app.dependencies import DbDep

router = APIRouter(prefix="/demo", tags=["SIH Demonstration"])


@router.post("/seed", response_model=dict, status_code=status.HTTP_200_OK)
async def seed_demo_dataset_endpoint(db: DbDep):
    """
    1-Click reset/seed for the complete fictional SIH demonstration dataset.
    Idempotent and safe to run anytime during SIH evaluations or rehearsals.
    """
    result = await seed_sih_demonstration_data(db)
    return ok(result, message="Complete fictional SIH demonstration dataset loaded successfully.")


@router.get("/personas", response_model=dict)
async def list_demo_personas():
    """
    Quick-reference list of demo login credentials across all roles.
    """
    personas = [
        {
            "role_title": "NGO Representative (Helping Villages Foundation)",
            "email": "lead@helpingvillages.org",
            "password": "NgoPassword123!",
            "name": "Ramesh Verma",
            "organization": "Helping Villages Foundation",
            "role": "NGO",
        },
        {
            "role_title": "NGO Representative (Rural Community Initiative)",
            "email": "lead@ruralcommunity.org",
            "password": "NgoPassword123!",
            "name": "Priya Nair",
            "organization": "Rural Community Initiative",
            "role": "NGO",
        },
        {
            "role_title": "Independent Platform Auditor",
            "email": "auditor@sih.gov.in",
            "password": "AuditorPassword123!",
            "name": "Inspector Suresh Sharma",
            "organization": "Independent Audit Panel",
            "role": "AUDITOR",
        },
        {
            "role_title": "Public Donor / Philanthropist",
            "email": "donor@philanthropy.org",
            "password": "DonorPassword123!",
            "name": "Ananya Patel",
            "organization": "Public Donor",
            "role": "DONOR",
        },
        {
            "role_title": "Platform Administrator",
            "email": "admin@transparency.gov.in",
            "password": "AdminPassword123!",
            "name": "Platform Administrator",
            "organization": "SIH Transparency Platform",
            "role": "ADMIN",
        },
    ]
    return ok(personas)
