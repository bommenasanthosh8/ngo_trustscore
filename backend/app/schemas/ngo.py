"""
NGO Pydantic schemas — request and response contracts for NGO onboarding & admin verification.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import NGOVerificationStatus


# ── Create NGO Request ─────────────────────────────────────────────────────────
class NGOCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=500, description="Official name of the NGO")
    registration_number: str = Field(..., min_length=2, max_length=100, description="Official registration / legal number")
    description: Optional[str] = Field(None, max_length=5000, description="Organization description and mission")
    address: Optional[str] = Field(None, max_length=1000, description="Registered physical address")
    contact_email: Optional[EmailStr] = Field(None, description="Official contact email")
    contact_phone: Optional[str] = Field(None, max_length=50, description="Contact phone number")
    website: Optional[str] = Field(None, max_length=500, description="Official website URL")
    authorized_representative: Optional[str] = Field(None, max_length=255, description="Name of authorized representative")

    # verification_status is explicitly excluded; always initialized to PENDING on creation.


# ── Update NGO Request ─────────────────────────────────────────────────────────
class NGOUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    address: Optional[str] = Field(None, max_length=1000)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=500)
    authorized_representative: Optional[str] = Field(None, max_length=255)

    # Note: verification_status cannot be changed by NGO via PATCH /ngos/{id}.
    model_config = ConfigDict(extra="forbid")


# ── Admin Rejection Request ───────────────────────────────────────────────────
class AdminRejectNGORequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=1000, description="Administrative reason for rejection")


# ── NGO Detailed Response ─────────────────────────────────────────────────────
class NGOResponse(BaseModel):
    id: uuid.UUID
    name: str
    registration_number: str
    darpan_id: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    website: Optional[str] = None
    authorized_representative: Optional[str] = None
    verification_status: NGOVerificationStatus
    is_verified: bool
    rejection_reason: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    project_count: Optional[int] = None
    transparency_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class NGOPublicSummary(BaseModel):
    """Enriched summary DTO for public NGO search and directory listings."""
    id: uuid.UUID
    name: str
    registration_number: str
    description: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    verification_status: NGOVerificationStatus
    is_verified: bool
    project_count: int = 0
    verified_project_count: int = 0
    transparency_score: Optional[float] = None
    project_categories: list[str] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

