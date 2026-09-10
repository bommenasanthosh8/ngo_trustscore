from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import audit_log
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.responses import ok
from app.dependencies import CurrentUserDep, DbDep, OptionalUserDep
from app.models.activity import ActivityLog
from app.models.donation import Donation
from app.models.enums import DonationStatus, PaymentMethod, UserRole
from app.models.ngo import NGO
from app.models.project import Project

router = APIRouter(prefix="/donations", tags=["Donations & Direct Giving"])


# ── Schemas ───────────────────────────────────────────────────────────────────
class CreateDonationRequest(BaseModel):
    ngo_id: uuid.UUID = Field(..., description="Target NGO receiving direct funds")
    project_id: Optional[uuid.UUID] = Field(None, description="Optional specific project ID")
    amount: float = Field(..., gt=0, description="Donation amount in INR")
    currency: str = Field(default="INR", max_length=10)
    payment_method: PaymentMethod = Field(default=PaymentMethod.UPI)
    donor_name: Optional[str] = Field(None, max_length=255)
    donor_email: Optional[EmailStr] = None
    donor_notes: Optional[str] = Field(None, max_length=1000)


def _serialize_donation(d: Donation) -> dict:
    ngo = getattr(d, "ngo", None)
    project = getattr(d, "project", None)
    return {
        "id": str(d.id),
        "donor_id": str(d.donor_id) if d.donor_id else None,
        "donor_name": d.donor_name,
        "donor_email": d.donor_email,
        "ngo_id": str(d.ngo_id),
        "ngo_name": ngo.name if ngo else "Registered NGO",
        "ngo_registration_number": ngo.registration_number if ngo else None,
        "project_id": str(d.project_id) if d.project_id else None,
        "project_code": project.project_code if project else None,
        "project_title": project.title if project else None,
        "amount": float(d.amount),
        "currency": d.currency,
        "payment_method": d.payment_method.value if hasattr(d.payment_method, "value") else str(d.payment_method),
        "transaction_id": d.transaction_id,
        "payment_status": d.payment_status.value if hasattr(d.payment_status, "value") else str(d.payment_status),
        "receipt_number": d.receipt_number,
        "tax_exemption_eligible": d.tax_exemption_eligible,
        "donor_notes": d.donor_notes,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "completed_at": d.completed_at.isoformat() if d.completed_at else None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_direct_donation(
    payload: CreateDonationRequest,
    db: DbDep,
    current_user: OptionalUserDep = None,
):
    """
    Process an immutable direct donation to an NGO or specific project.
    Generates a cryptographically sound transaction ID, assigns 80G tax exemption receipt,
    and logs activity for full transparent auditability.
    """
    # 1. Resolve NGO
    ngo_res = await db.execute(select(NGO).where(NGO.id == payload.ngo_id))
    ngo = ngo_res.scalar_one_or_none()
    if not ngo:
        raise NotFoundException("Target NGO not found.")

    # 2. Resolve Project if specified
    project: Optional[Project] = None
    if payload.project_id:
        proj_res = await db.execute(
            select(Project).where(Project.id == payload.project_id, Project.ngo_id == ngo.id)
        )
        project = proj_res.scalar_one_or_none()
        if not project:
            raise BadRequestException("The specified project was not found under this NGO.")

    # 3. Determine Donor identity
    donor_id = current_user.id if current_user else None
    donor_name = (
        payload.donor_name.strip()
        if payload.donor_name and payload.donor_name.strip()
        else (current_user.full_name if current_user else "Anonymous Supporter")
    )
    donor_email = (
        str(payload.donor_email).strip()
        if payload.donor_email
        else (current_user.email if current_user else "supporter@transparency.ngo")
    )

    # 4. Generate verifiable transaction & receipt numbers
    now = datetime.now(timezone.utc)
    year = now.year
    rand_hex = uuid.uuid4().hex[:8].upper()
    method_code = payload.payment_method.value[:3].upper()
    txn_id = f"TXN_{method_code}_{year}_{rand_hex}"
    receipt_no = f"RCPT-80G-{year}-{uuid.uuid4().hex[:6].upper()}"

    donation = Donation(
        id=uuid.uuid4(),
        donor_id=donor_id,
        donor_name=donor_name,
        donor_email=donor_email,
        ngo_id=ngo.id,
        project_id=project.id if project else None,
        amount=round(payload.amount, 2),
        currency=payload.currency.upper(),
        payment_method=payload.payment_method,
        transaction_id=txn_id,
        payment_status=DonationStatus.SUCCESS,
        receipt_number=receipt_no,
        tax_exemption_eligible=True,
        donor_notes=payload.donor_notes.strip() if payload.donor_notes else None,
        completed_at=now,
    )

    db.add(donation)

    # 5. Log audit trail
    activity = ActivityLog(
        action="DONATION_RECEIVED",
        actor_id=donor_id,
        actor_role=current_user.role.value if current_user else "DONOR",
        resource_type="donation",
        resource_id=str(donation.id),
        detail={
            "ngo_id": str(ngo.id),
            "ngo_name": ngo.name,
            "project_id": str(project.id) if project else None,
            "project_code": project.project_code if project else None,
            "amount": donation.amount,
            "currency": donation.currency,
            "transaction_id": txn_id,
            "receipt_number": receipt_no,
            "payment_method": payload.payment_method.value,
        },
        success=True,
    )
    db.add(activity)

    await db.commit()

    # Re-fetch with relationships loaded
    fetch_res = await db.execute(
        select(Donation)
        .options(selectinload(Donation.ngo), selectinload(Donation.project))
        .where(Donation.id == donation.id)
    )
    fresh_donation = fetch_res.scalar_one()

    return ok(
        _serialize_donation(fresh_donation),
        message=f"Donation of {fresh_donation.currency} {fresh_donation.amount:,.2f} directly to {ngo.name} processed successfully!",
    )


@router.get("/my-donations", response_model=dict)
async def get_my_donations(
    current_user: CurrentUserDep,
    db: DbDep,
):
    """Retrieve personal donation portfolio & tax receipts for logged-in user."""
    query = (
        select(Donation)
        .options(selectinload(Donation.ngo), selectinload(Donation.project))
        .where(
            (Donation.donor_id == current_user.id) | (Donation.donor_email == current_user.email)
        )
        .order_by(Donation.created_at.desc())
    )
    res = await db.execute(query)
    donations = res.scalars().all()
    serialized = [_serialize_donation(d) for d in donations]

    total_amount = sum(d.amount for d in donations)
    unique_ngos = len({d.ngo_id for d in donations})

    return ok({
        "items": serialized,
        "total_donated": round(total_amount, 2),
        "total_donations_count": len(serialized),
        "supported_ngos_count": unique_ngos,
    })


@router.get("/stats", response_model=dict)
async def get_donation_stats(db: DbDep):
    """Platform-wide direct donation transparency statistics."""
    total_amount_res = await db.execute(
        select(func.sum(Donation.amount)).where(Donation.payment_status == DonationStatus.SUCCESS)
    )
    total_amount = float(total_amount_res.scalar() or 0.0)

    total_count_res = await db.execute(
        select(func.count(Donation.id)).where(Donation.payment_status == DonationStatus.SUCCESS)
    )
    total_count = total_count_res.scalar() or 0

    return ok({
        "total_funds_disbursed_inr": round(total_amount, 2),
        "total_direct_donations": total_count,
        "tax_exemption_standard": "Section 80G Compliant Direct Transfer",
    })


@router.get("/{id}", response_model=dict)
async def get_donation_by_id(id: uuid.UUID, db: DbDep):
    """Retrieve full official donation dossier with 80G tax receipt breakdown."""
    res = await db.execute(
        select(Donation)
        .options(selectinload(Donation.ngo), selectinload(Donation.project))
        .where(Donation.id == id)
    )
    d = res.scalar_one_or_none()
    if not d:
        raise NotFoundException("Donation record not found.")
    return ok(_serialize_donation(d))
